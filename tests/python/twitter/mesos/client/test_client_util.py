import json
import os
import pytest
import tempfile

from twitter.mesos.client import client_util
from twitter.common.contextutil import temporary_dir, temporary_file, open_zip
from twitter.mesos.config.schema import Announcer, Job, Resources, Task, MB
from twitter.mesos.packer import sd_packer_client
import twitter.mesos.packer.packer_client as packer_client
from twitter.mesos.parsers.mesos_config import MesosConfig
from twitter.mesos.parsers.proxy_config import ProxyConfig
from twitter.mesos.parsers.pystachio_config import PystachioConfig

from mox import Mox, IsA

def test_zip_package_files():
  job_name = 'spangled'
  text = '''O say can you see by the dawn's early light,'''
  with temporary_dir(root_dir=os.getcwd()) as tmp_dir:
    # prepare the files
    package_files = []
    package_file_names = []
    basenames = []
    for i in range(10):
      f = tempfile.NamedTemporaryFile('w')
      f.write(text)
      f.flush()
      package_files.append(f)
      package_file_names.append(f.name)
      basenames.append(os.path.basename(f.name))
    tmp_dir = tempfile.mkdtemp()
    # run the test
    zipname = client_util._zip_package_files(job_name, package_file_names, tmp_dir)
    # verify
    assert zipname == os.path.join(tmp_dir, MesosConfig.get_package_files_zip_name(job_name))
    assert os.path.isfile(zipname)
    with open_zip(zipname, 'r') as zipf:
      zipf.testzip()
      assert basenames == zipf.namelist()


def test_get_and_verify_metadata():
  def run(package_version, expect_success):
    mocker = Mox()
    if not expect_success:
      mocker.StubOutWithMock(client_util, 'die')
      client_util.die(IsA(str)).AndRaise(SystemExit)
    mocker.ReplayAll()
    if expect_success:
      client_util._get_and_verify_metadata(package_version)
    else:
      with pytest.raises(SystemExit):
        client_util._get_and_verify_metadata(package_version)
    mocker.UnsetStubs()
    mocker.VerifyAll()

  base_metada = {'md5sum': '0x42'}
  base_package_version =  {
    'id': 1,
    'metadata': unicode(json.dumps(base_metada))
  }

  # 0. success
  run(base_package_version, expect_success=True)

  # 1. no package id.
  package_version_no_id = dict(base_package_version)
  package_version_no_id.pop('id')
  run(package_version_no_id, expect_success=False)

  # 2. no metadata.
  package_version_no_metadata = dict(base_package_version)
  package_version_no_metadata.pop('metadata')
  run(package_version_no_metadata, expect_success=False)

  # 3. metadata with no md5sum.
  package_version_no_md5sum = dict(base_package_version)
  package_version_no_md5sum['metadata'] =\
  unicode(json.dumps({'sheep': 'baa baa'}))
  run(package_version_no_md5sum, expect_success=False)

  # 4. metadata is not a string.
  package_version_no_string = dict(base_package_version)
  package_version_no_string['metadata'] = 22
  run(package_version_no_string, expect_success=False)

  # 5. metadata is not valid json.
  package_version_no_json = dict(base_package_version)
  package_version_no_json['metadata'] = unicode("22 && (")
  run(package_version_no_json, expect_success=False)


def _prepare_mocks_for_packer_and_files():
  mocker = Mox()
  cluster = 'smf1'
  role = 'jack'
  name = 'jobname'
  package_files = ['tom', 'dick', 'harry']

  tmp_dir = '/var/tmp/foo'
  mocker.StubOutWithMock(tempfile, 'mkdtemp')
  tempfile.mkdtemp(dir=os.getcwd()).AndReturn(tmp_dir)

  packer = packer_client.Packer('host', 'port')
  mocker.StubOutWithMock(sd_packer_client, 'create_packer')
  sd_packer_client.create_packer(cluster).AndReturn(packer)

  zip_name = os.path.join(tmp_dir, MesosConfig.get_package_files_zip_name(name))
  mocker.StubOutWithMock(client_util, '_zip_package_files')
  client_util._zip_package_files(name, package_files, tmp_dir).AndReturn(zip_name)

  digest = '0x42'
  mocker.StubOutWithMock(packer_client.Packer, 'compute_checksum')
  packer_client.Packer.compute_checksum(zip_name).AndReturn(digest)

  return (mocker, cluster, role, name, package_files, tmp_dir,
          packer, zip_name, digest)


def test_get_package_uri_from_packer_and_files_success():
  def run(do_upload, first_version):
    assert not(not do_upload and first_version)

    (mocker, cluster, role, name, package_files, tmp_dir,
     packer, zip_name, digest) = _prepare_mocks_for_packer_and_files()

    package_name = name + client_util._PACKAGE_FILES_SUFFIX
    package_version = None
    mocker.StubOutWithMock(packer, 'get_version')
    if do_upload:
      if first_version:
        packer.get_version(role, package_name, 'latest').AndRaise(packer_client.Packer.Error())
      else:
        package_digest = '0x99'  # different digest => must upload
        metadata = {'md5sum': package_digest}
        package_version = {'id': '1', 'metadata': unicode(json.dumps(metadata))}
        packer.get_version(role, package_name, 'latest').AndReturn(package_version)
    else:
      metadata = {'md5sum': digest}
      package_version = {'id': '1', 'metadata': unicode(json.dumps(metadata))}
      packer.get_version(role, package_name, 'latest').AndReturn(package_version)

    if do_upload:
      metadata =  {'md5sum': digest}
      mocker.StubOutWithMock(packer, 'add')
      packer.add(role, package_name, zip_name, unicode(json.dumps(metadata)), digest)
      if not first_version:
        mocker.StubOutWithMock(packer, 'delete')
        packer.delete(role, package_name, package_version['id'])

    package_tuple = (role, package_name, 'latest')
    mocker.StubOutWithMock(client_util, '_get_package_data')
    package_version = {'id': '1', 'metadata': unicode(json.dumps(metadata))}
    client_util._get_package_data(cluster, package_tuple, packer).AndReturn(package_version)

    mocker.StubOutWithMock(client_util, '_extract_package_uri')
    client_util._extract_package_uri(package_version)

    mocker.ReplayAll()
    client_util._get_package_uri_from_packer_and_files(
      cluster, role, name, package_files)
    mocker.UnsetStubs()
    mocker.VerifyAll()

  # Succeeds when uploading first version.
  run(do_upload=True, first_version=True)

  # Succeeds when uploading later versions.
  run(do_upload=True, first_version=False)

  # Succeeds when not uploading
  run(do_upload=False, first_version=False)


def test_get_package_uri_from_packer_and_files_fail_invalid_package_version():
  (mocker, cluster, role, name, package_files, tmp_dir,
   packer, zip_name, digest) = _prepare_mocks_for_packer_and_files()
  package_name = name + client_util._PACKAGE_FILES_SUFFIX
  package_version = {}
  mocker.StubOutWithMock(packer, 'get_version')
  packer.get_version(role, package_name, 'latest').AndReturn(package_version)
  mocker.StubOutWithMock(client_util, '_get_and_verify_metadata')
  client_util._get_and_verify_metadata(package_version).AndRaise(SystemExit)
  mocker.ReplayAll()
  with pytest.raises(SystemExit):
   client_util._get_package_uri_from_packer_and_files(cluster, role, name, package_files)
  mocker.UnsetStubs()
  mocker.VerifyAll()


MESOS_CONFIG_BASE = """
HELLO_WORLD = Job(
  name = 'hello_world',
  role = 'john_doe',
  cluster = 'smf1-test',
  %s
  task = Task(
    name = 'main',
    processes = [Process(name = 'hello_world', cmdline = 'echo {{thermos.ports[http]}}')],
    resources = Resources(cpu = 0.1, ram = 64 * MB, disk = 64 * MB),
  )
)
jobs = [HELLO_WORLD]
"""

MESOS_CONFIG_WITH_ANNOUNCE_1 = MESOS_CONFIG_BASE % 'announce = Announcer(primary_port="http"),'
MESOS_CONFIG_WITH_ANNOUNCE_2 = MESOS_CONFIG_BASE % (
 '''announce = Announcer(
       primary_port = "http",
       portmap = {"aurora": "http"}),
 ''')
MESOS_CONFIG_WITH_INVALID_STATS = MESOS_CONFIG_BASE % (
    'announce = Announcer(primary_port="http", stats_port="blah"),')
MESOS_CONFIG_WITHOUT_ANNOUNCE = MESOS_CONFIG_BASE % ''


def test_get_config_announces():
  for good_config in (MESOS_CONFIG_WITH_ANNOUNCE_1, MESOS_CONFIG_WITH_ANNOUNCE_2,
                      MESOS_CONFIG_WITHOUT_ANNOUNCE):
    with temporary_file() as fp:
      fp.write(good_config)
      fp.flush()
      client_util.get_config('hello_world', fp.name)


def test_environment_names():
  BAD = ('Prod', ' prod', 'prod ', 'tEst', 'production', 'staging 2', 'staging', 'stagingA')
  GOOD = ('prod', 'devel', 'test', 'staging001', 'staging1', 'staging1234')
  base_job = Job(
      name='hello_world', role='john_doe', cluster='smf1-test',
      task = Task(name='main', processes = [],
                  resources = Resources(cpu = 0.1, ram = 64 * MB, disk = 64 * MB)))

  client_util._validate_environment_name(PystachioConfig(base_job))
  for env_name in GOOD:
    client_util._validate_environment_name(PystachioConfig(base_job(environment=env_name)))
  for env_name in BAD:
    with pytest.raises(ValueError):
      client_util._validate_environment_name(PystachioConfig(base_job(environment=env_name)))


def test_dedicated_portmap():
  base_job = Job(
      name='hello_world', role='john_doe', cluster='smf1-test',
      task = Task(name='main', processes = [],
                  resources = Resources(cpu = 0.1, ram = 64 * MB, disk = 64 * MB)))

  client_util._validate_announce_configuration(PystachioConfig(base_job))
  client_util._validate_announce_configuration(
      PystachioConfig(base_job(constraints = {'dedicated': 'mesos-team'})))
  client_util._validate_announce_configuration(
      PystachioConfig(base_job(constraints = {'dedicated': 'mesos-team'},
                               announce = Announcer(portmap={'http': 80}))))

  with pytest.raises(ValueError):
    client_util._validate_announce_configuration(
        PystachioConfig(base_job(announce=Announcer(portmap={'http': 80}))))

  with pytest.raises(ValueError):
    client_util._validate_announce_configuration(
        PystachioConfig(base_job(announce=Announcer(portmap={'http': 80}),
                                 constraints = {'foo': 'bar'})))
