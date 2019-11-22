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

test_agent_ip = "192.168.33.7"

def test_http_example_basic(cluster, role, env, base_config, updated_config, bad_healthcheck_config, job,
                            *bind_parameters):
    jobkey = f"{cluster}/{role}/{env}/{job}"

    test_create(config=base_config, jobkey=jobkey)
    test_observer_ui(cluster=cluster, role=role, job=job)
    test_kill(jobkey=jobkey)


def test_http_example(cluster, role, env, base_config, updated_config, bad_healthcheck_config, job, *bind_parameters):
    jobkey = f"{cluster}/{role}/{env}/{job}"
    task_id_prefix = f"{role}-{env}-{job}-0"
    discovery_name = f"{job}.{env}.{role}"

   #  test_config(config=base_config, jobkey=jobkey)
    # test_inspect(config=base_config, jobkey=jobkey)
    test_create(config=base_config, jobkey=jobkey)
    # test_job_status(jobkey=jobkey)
    # test_scheduler_ui(role=role, env=env, job=job)
   #  test_observer_ui(cluster=cluster, role=role, job=job)
    # test_discovery_info(task_id_prefix=task_id_prefix, discovery_name=discovery_name)
   #  test_thermos_profile(jobkey=jobkey)
   #  test_file_mount(jobkey=jobkey)
    #test_restart(jobkey=jobkey)
    test_update_add_only_kill_only(jobkey=jobkey,config=base_config,cluster=cluster)
    #test_update(jobkey=jobkey,config=base_config,cluster=cluster)
    #test_update_fail(jobkey=jobkey,config=base_config,cluster=cluster)
    #test_update(jobkey=jobkey,config=base_config,cluster=cluster)
    #test_announce(role=role, env=env, job=job)
    #test_run(jobkey=jobkey)
    #test_kill(jobkey=jobkey)
    #test_quota(

def check_output(opts):
    return subprocess.check_output(opts, text=True, stderr=subprocess.DEVNULL)

def test_config(config, jobkey):
    config_list = check_output(["aurora", "config", "list", config])
    if config_list.find(jobkey) >= 0:
        return True
    else:
        return False


def test_inspect(jobkey, config, *bind_parameters):
    subprocess.run(["aurora", "job", "inspect", jobkey, config])


def test_create(jobkey, config, *bind_parameters):
    subprocess.run(["aurora", "job", "create", jobkey, config])


def test_job_status(jobkey):
    subprocess.run(["aurora", "job", "list", jobkey], capture_output=True)
    subprocess.run(["aurora", "job", "status", jobkey])


def test_scheduler_ui(role, env, job):
    base_url = f"http://{test_agent_ip}:8081/"

    endpoints = ("leaderhealth", "scheduler", f"scheduler/{role}", f"scheduler/{role}/{env}/{job}")

    for endpoint in endpoints:
        r = requests.get(f"{base_url}{endpoint}")
        if r.status_code != requests.codes.ok:
            return False


def test_observer_ui(cluster, role, job):
    observer_url = f"http://{test_agent_ip}:1338"
    r = requests.get(observer_url)
    if r.status_code != requests.codes.ok:
        return False

    for _ in range(120):
        task_id = check_output(
            ["aurora_admin", "query", "-l", "%taskId%", "--shards=0", "--states=RUNNING", cluster, role, job])

        task_url = f"{observer_url}/task/{task_id}"
        r = requests.get(task_url.strip())
        if r.status_code == requests.codes.ok:
            return True
        else:
            time.sleep(1)

    return False


def test_discovery_info(task_id_prefix, discovery_name):
    r = requests.get(f"http://{test_agent_ip}:5050/state")
    if r.status_code != requests.codes.ok:
        return False

    framework_info = {}
    for framework in r.json()["frameworks"]:
        if framework["name"] == "Aurora":
            framework_info = framework

    if not framework_info:
        return False

    task_info = {}
    if not framework_info["tasks"]:
        return False

    for task in framework_info["tasks"]:
        if task["id"].startswith(task_id_prefix):
            task_info = task

    if "discovery" not in task_info:
        return False

    discovery_info = task_info["discovery"]
    if "name" not in discovery_info or discovery_info["name"] != discovery_name:
        return False

    if "ports" not in discovery_info or "ports" not in discovery_info["ports"]:
        return False

    if len(discovery_info["ports"]["ports"]) == 0:
        return False

    return True


def test_thermos_profile(jobkey):
    contents = subprocess.check_output(
        ["aurora", "task", "ssh", f"{jobkey}/0", "--command=tail -1 .logs/read_env/0/stdout"],
        text=True)

    if contents.strip() != "hello":
        return False

    return True


def test_file_mount(jobkey):
    aurora_version = check_output(
        ["aurora", "task", "ssh", f"{jobkey}/0", "--command=tail -1 .logs/verify_file_mount/0/stdout"]
        )

    with open("/vagrant/.auroraversion") as version:
        if aurora_version.strip() != version.read().strip():
            return False

    return True


def test_restart(jobkey):
    subprocess.run(["aurora", "job", "restart", "--batch-size=2", "--watch-secs=10", jobkey])


def test_update_add_only_kill_only(jobkey, config, cluster, *bind_parameters):
    subprocess.run(["aurora", "update", "start", jobkey, config, "--bind=profile.instances=3"])

    update_id = assert_active_update_state(jobkey=jobkey, expected_state="ROLLING_FORWARD")

    if update_id == "":
        return False

    subprocess.run(["aurora", "update", "wait", jobkey, update_id])

    assert_update_state_by_id(jobkey=jobkey, update_id=update_id, expected_state="ROLLED_FORWARD")
    wait_until_task_counts(jobkey=jobkey, expected_running=3, expected_pending=0)


def test_update(jobkey, updated_config, cluster, bind_parameters):
    pass


def test_update_fail(jobkey, base_config, cluster, bad_healthcheck_config, bind_parameters):
    pass


def test_announce(role, env, job):
    pass


def test_run(jobkey):
    proc = subprocess.check_ouput(["aurora", "task", "run", f"{jobkey}", "ls -a"], text=True)

    print(proc)

    pass


def test_quota(cluster, role):
    subprocess.run(["aurora", "quota", "get", f"{cluster}/{role}"])


def test_kill(jobkey, *args):
    subprocess.run(["aurora", "job", "kill", f"{jobkey}/1"])
    subprocess.run(["aurora", "job", "killall", jobkey])


def assert_active_update_state(jobkey, expected_state):
    statuses = json.loads(check_output(["aurora", "update", "list", jobkey, "--status=active", "--write-json"]))

    if len(statuses) == 0:
        return ""

    if statuses[0]["status"] != expected_state:
        return ""

    return statuses[0]["id"]


def assert_update_state_by_id(jobkey, update_id, expected_state):
    update_info = json.loads(
        check_output(
            ["aurora", "update", "info", jobkey, update_id, "--write-json"]
            ))

    if "status" not in update_info or update_info["status"] != expected_state:
        return False

    return True


def wait_until_task_counts(jobkey, expected_running, expected_pending):
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
    test_http_example(
        cluster=test_cluster,
        role=test_role,
        env=test_env,
        base_config=test_config_file,
        updated_config=test_config_updated_file,
        bad_healthcheck_config=test_bad_healthcheck_config_updated_file,
        job=test_job_docker)


main()