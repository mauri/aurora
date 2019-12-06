#!/usr/bin/python3
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# from apache.aurora.client.cli.client import AuroraCommandLine

import subprocess
import requests
import time
import json
import pytest

test_agent_ip = "192.168.33.7"


def get_jobkey(cluster, role, env, job):
    return f"{cluster}/{role}/{env}/{job}"


def get_task_id_prefix(cluster, role, env, job):
    return f"{role}-{env}-{job}-0"


def get_discovery_name(cluster, role, env, job):
    return f"{job}.{env}.{role}"


def setup(test_root="/vagrant/src/test/sh/org/apache/aurora/e2e/"):
    check_output([test_root+"setup.sh"])


def xtest_http_example_basic_revolcable():
    _run_test_http_example_basic(job="http_example_revocable")


def xtest_http_example_basic_gpu():
    _run_test_http_example_basic(job="http_example_gpu")


def test_http_example_basic():
    setup()
    _run_test_http_example_basic(job="http_example")


def _run_test_http_example_basic(job):
    test_root = "/vagrant/src/test/sh/org/apache/aurora/e2e/"
    example_dir = test_root + "http/"
    _cluster = "devcluster"
    _role = "vagrant"
    _env = "test"
    _config_file = example_dir + "http_example.aurora"
    _config_updated_file = example_dir + "http_example_updated.aurora"
    _bad_healthcheck_config_updated_file = example_dir + "http_example_bad_healthcheck.aurora"

    jobkey = get_jobkey(_cluster, _role, _env, job)

    assert_jobkey_in_config_list(jobkey=jobkey, config_path=_config_file)
    assert_jobkey_inspect(jobkey=jobkey, config_path=_config_file, )
    assert_create(jobkey, _config_file)  # test_create $_jobkey $_base_config
    assert_job_status(jobkey)
    assert_scheduler_ui(_cluster, _role, _env, job)
    assert_observer_ui(_cluster, _role, _env, job)  # test_observer_ui $_cluster $_role $_job
    assert_discovery_info(_cluster, _role, _env, job)   # "${_role}-${_env}-${_job}-0"
    assert_thermos_profile(jobkey)
    assert_file_mount(_cluster, _role, _env, job)
    assert_killall(jobkey)  # test_kill $_jobkey


# Original Bash:
    # test_config $_base_config $_jobkey                                                    X
    # test_inspect $_jobkey $_base_config $_bind_parameters                                 X
    # test_create $_jobkey $_base_config $_bind_parameters                                  X
    # test_job_status $_cluster $_role $_env $_job                                          X
    # test_scheduler_ui $_role $_env $_job                                                  X
    # test_observer_ui $_cluster $_role $_job                                               X
    # test_discovery_info $_task_id_prefix $_discovery_name                                 X
    # test_thermos_profile $_jobkey                                                         X
    # test_file_mount $_cluster $_role $_env $_job
    # test_restart $_jobkey
    # test_update_add_only_kill_only $_jobkey $_base_config $_cluster $_bind_parameters
    # test_update $_jobkey $_updated_config $_cluster $_bind_parameters
    # test_update_fail $_jobkey $_base_config  $_cluster $_bad_healthcheck_config $_bind_parameters
    # # Running test_update second time to change state to success.
    # test_update $_jobkey $_updated_config $_cluster $_bind_parameters
    # test_announce $_role $_env $_job
    # test_run $_jobkey
    # # TODO(AURORA-1926): 'aurora task scp' only works fully on Mesos containers (can only read for
    # # Docker). See if it is possible to enable write for Docker sandboxes as well then remove the
    # # 'if' guard below.
    # if [[ $_job != *"docker"* ]]; then
    # test_scp_success $_jobkey
    # test_scp_permissions $_jobkey
    # fi
    # test_kill $_jobkey
    # test_quota $_cluster $_role
# Python Translation:
    # test_inspect(config=base_config, jobkey=jobkey)
    # a_create(config=base_config, jobkey=jobkey)
    # a_job_status(jobkey=jobkey)
    # a_scheduler_ui(role=role, env=env, job=job)
    # a_observer_ui(cluster=cluster, role=role, job=job)
    # test_discovery_info(task_id_prefix=task_id_prefix, discovery_name=discovery_name)
    #  test_thermos_profile(jobkey=jobkey)
    #  test_file_mount(jobkey=jobkey)
    # test_restart(jobkey=jobkey)
    # a_test_update_add_only_kill_only(jobkey=jobkey, config=base_config, cluster=cluster)
    # test_update(jobkey=jobkey,config=base_config,cluster=cluster)
    # test_update_fail(jobkey=jobkey,config=base_config,cluster=cluster)
    # test_update(jobkey=jobkey,config=base_config,cluster=cluster)
    # test_announce(role=role, env=env, job=job)
    # test_run(jobkey=jobkey)
    # a_test_kill(jobkey=jobkey)
    # test_quota(


def assert_jobkey_in_config_list(jobkey, config_path):
    assert jobkey in check_output(["aurora", "config", "list", config_path])


def assert_jobkey_inspect(jobkey, config_path):
    check_output(["aurora", "job", "inspect", jobkey, config_path])


def check_output(opts):
    return subprocess.check_output(opts, text=True, stderr=subprocess.DEVNULL)


def a_inspect(jobkey, config, *bind_parameters):
    subprocess.run(["aurora", "job", "inspect", jobkey, config])


def assert_create(jobkey, config, *bind_parameters):
    subprocess.check_output(["aurora", "job", "create", jobkey, config])


def assert_job_status(jobkey):
    check_output(["aurora", "job", "list", jobkey])
    assert check_output(["aurora", "job", "status", jobkey])


def assert_scheduler_ui(_cluster, role, env, job):
    base_url = f"http://{test_agent_ip}:8081/"

    endpoints = ("leaderhealth", "scheduler", f"scheduler/{role}", f"scheduler/{role}/{env}/{job}")

    for endpoint in endpoints:
        r = requests.get(f"{base_url}{endpoint}")
        assert r.status_code == requests.codes.ok


def assert_observer_ui(cluster, role, env, job):
    observer_url = f"http://{test_agent_ip}:1338"
    r = requests.get(observer_url)
    assert r.status_code == requests.codes.ok

    for _ in range(120):
        task_id = check_output(
            ["aurora_admin", "query", "-l", "%taskId%", "--shards=0", "--states=RUNNING", cluster, role, job])
        task_url = f"{observer_url}/task/{task_id}"
        r = requests.get(task_url.strip())
        if r.status_code == requests.codes.ok:
            return
        else:
            print(f"waiting for running task {job}...")
            time.sleep(1)

    assert False, f"timeout waiting for task {cluster}/{role}/{env}/{job} in state RUNNING"


def assert_discovery_info(cluster, role, env, job):
    task_id_prefix = get_task_id_prefix(cluster, role, env, job)
    discovery_name = get_discovery_name(cluster, role, env, job)
    r = requests.get(f"http://{test_agent_ip}:5050/state")
    if r.status_code != requests.codes.ok:
        assert False, f"error getting mesos agent state"

    framework_info = {}
    for framework in r.json()["frameworks"]:
        if framework["name"] == "Aurora":
            framework_info = framework

    if not framework_info:
        assert False, f"Cannot get Aurora framework info from {r.json()}"

    task_info = None
    if not framework_info["tasks"]:
        assert False, f"Cannot get tasks from {framework_info}"

    for task in framework_info["tasks"]:
        if task["id"].startswith(task_id_prefix):
            task_info = task

    assert task_info is not None, f"Cannot find task with prefix id {task_id_prefix} in {framework_info['tasks']}"
    assert "discovery" in task_info, f"Cannot get discovery info json from task blob {task_info}"
    discovery_info = task_info["discovery"]
    assert "name" in discovery_info and discovery_info["name"] == discovery_name
    assert "ports" in discovery_info and "ports" in discovery_info["ports"]
    assert len(discovery_info["ports"]["ports"]) > 0


def assert_thermos_profile(jobkey):
    contents = subprocess.check_output(["aurora", "task", "ssh", f"{jobkey}/0",
                                        "--command=tail -1 .logs/read_env/0/stdout"])
    assert contents.strip() == b"hello"


def assert_file_mount(cluster, role, env, job):
    if job != 'http_example_unified_docker':
        return

    aurora_version = check_output(
        ["aurora", "task", "ssh", f"{get_jobkey(cluster, role, env, job)}/0",
         "--command=tail -1 .logs/verify_file_mount/0/stdout"]
    )
    with open("/vagrant/.auroraversion") as version:
        assert aurora_version.strip() == version.read().strip()


def a_test_restart(jobkey):
    subprocess.run(["aurora", "job", "restart", "--batch-size=2", "--watch-secs=10", jobkey])


def a_test_update_add_only_kill_only(jobkey, config, cluster, *bind_parameters):
    subprocess.run(["aurora", "update", "start", jobkey, config, "--bind=profile.instances=3"])

    update_id = a_assert_active_update_state(jobkey=jobkey, expected_state="ROLLING_FORWARD")

    if update_id == "":
        return False

    subprocess.run(["aurora", "update", "wait", jobkey, update_id])

    a_assert_update_state_by_id(jobkey=jobkey, update_id=update_id, expected_state="ROLLED_FORWARD")
    a_wait_until_task_counts(jobkey=jobkey, expected_running=3, expected_pending=0)


def a_test_update(jobkey, updated_config, cluster, bind_parameters):
    pass


def a_test_update_fail(jobkey, base_config, cluster, bad_healthcheck_config, bind_parameters):
    pass


def a_test_announce(role, env, job):
    pass


def a_test_run(jobkey):
    proc = subprocess.check_ouput(["aurora", "task", "run", f"{jobkey}", "ls -a"], text=True)

    print(proc)

    pass


def a_test_quota(cluster, role):
    subprocess.run(["aurora", "quota", "get", f"{cluster}/{role}"])


def assert_killall(jobkey, *args):
    # subprocess.run(["aurora", "job", "kill", f"{jobkey}/1"])
    subprocess.run(["aurora", "job", "killall", jobkey])


def a_assert_active_update_state(jobkey, expected_state):
    statuses = json.loads(check_output(["aurora", "update", "list", jobkey, "--status=active", "--write-json"]))

    if len(statuses) == 0:
        return ""

    if statuses[0]["status"] != expected_state:
        return ""

    return statuses[0]["id"]


def a_assert_update_state_by_id(jobkey, update_id, expected_state):
    update_info = json.loads(
        check_output(
            ["aurora", "update", "info", jobkey, update_id, "--write-json"]
        ))

    if "status" not in update_info or update_info["status"] != expected_state:
        return False

    return True


def a_wait_until_task_counts(jobkey, expected_running, expected_pending):
    for _ in range(120):
        job_statuses = json.loads(
            check_output(
                ["aurora", "job", "status", jobkey, "--write-json"]
            ))

        if "active" not in job_statuses or len(job_statuses["active"]) == 0:
            time.sleep(20)

        print(job_statuses)
        running = 0
        pending = 0
        for task in job_statuses["active"]:
            if "status" not in task:
                continue
            if task["status"] == "RUNNING":
                running += 1
            if task["status"] == "PENDING":
                pending += 1

        if running == expected_running and pending == expected_pending:
            return True

    return False


def main():
    test_root = "/vagrant/src/test/sh/org/apache/aurora/e2e/"
    example_dir = test_root + "http/"

    test_cluster = "devcluster"
    test_role = "vagrant"
    test_env = "test"
    test_job = "http_example"
    test_config_file = example_dir + "http_example.aurora"
    test_config_updated_file = example_dir + "http_example_updated.aurora"
    test_bad_healthcheck_config_updated_file = example_dir + "http_example_bad_healthcheck.aurora"
    test_job_docker = "http_example_docker"

    # Basic HTTP Server Test
    # test_http_example_basic(test_cluster, test_role, test_env, test_config_file, test_config_updated_file,
    # test_bad_healthcheck_config_updated_file, test_job, "")

    # Test Job
    #  test_http_example(
    #      test_cluster,
    #      test_role,
    #      test_env,
    #      test_config_file,
    #      test_config_updated_file,
    #      test_bad_healthcheck_config_updated_file,
    #      "http_example",
    #      "")

    # Docker test
    test_http_example()


# main()
