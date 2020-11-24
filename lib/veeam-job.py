#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sergey Sedov <serge.eximius@gmail.com>
# GNU General Public License v3.0+ (see https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: veeam-job
short_description: Управлние задачами файлового бекапа veeam на linux
version_added: "0.1.0"

description: Позволяет создавать, удалять и просматривать задания бекапа. Поддерживает только файловый бекап (fileLevel).

options:
    type:
        description:
        - C(job) создание или удаление задачи файлового (fileLevel) бекапа.
        - C(list) список задач бекапа.
        required: true
        type: str
        choices: [ job, list ]
    state:
        description:
        - C(present) создание задачи бекапа.
        - C(absent) удаление задачи бекапа.
        type: str
        choices: [ absent, present ]
        required: false
        default: present
    prefreeze:
        description: Путь к скрипту для уровня prefreeze.
        type: path
        required: false
    includedirs:
        description: Путь к директории для бекапа. Обязательное для state C(present).
        type: path
        required: false
    name:
        description: Имя задачи бекапа. Обязательное для state C(present) и C(absent).
        type: str
        required: false
    reponame:
        description: Имя репозитория. Обязательное для state C(present).
        type: str
        required: false
    maxpoints:
        description: Глубина хранения.
        type: int
        required: false
    rundays:
        description: Дни запуска (Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, All). Обязательное для C(runat).
        type: int
        required: false
    runat:
        description: Время запуска HH:MM. Обязательное для C(rundays).
        type: int
        required: false

author:
    - Sergey Sedov (@sergeeximius)
'''

EXAMPLES = r'''
'''

RETURN = r'''
'''

import os
import subprocess
import select
import json

from ansible.module_utils._text import to_text
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import b

def cmd(command):
    # This is code from https://github.com/ansible/ansible/blob/devel/lib/ansible/modules/service.py
    # Copyright: (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
    # GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
    lang_env = dict(LANG='C', LC_ALL='C', LC_MESSAGES='C')
    p = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=lang_env)
    stdout = b("")
    stderr = b("")
    fds = [p.stdout, p.stderr]
    # Wait for all output, or until the main process is dead and its output is done.
    while fds:
        rfd, wfd, efd = select.select(fds, [], fds, 1)
        if not (rfd + wfd + efd) and p.poll() is not None:
            break
        if p.stdout in rfd:
            dat = os.read(p.stdout.fileno(), 4096)
            if not dat:
                fds.remove(p.stdout)
            stdout += dat
        if p.stderr in rfd:
            dat = os.read(p.stderr.fileno(), 4096)
            if not dat:
                fds.remove(p.stderr)
            stderr += dat
    p.wait()
    return (p.returncode, stdout, stderr)


def jobInfo(jobname):
    rc, stdout, stderr = cmd(["veeamconfig", "job", "info", "--name", jobname])
    ji = {}
    for line in to_text(stdout).split('\n'):
        if ("Repository name" in line):
            ji["reponame"] = line.split(':')[1].strip()
        if ("Pre-freeze command" in line):
            ji["prefreeze"] = line.split(':')[1].strip()
        if ("Include Directory" in line):
            ji["includedirs"] = line.split(':')[1].strip()
        if ("Max points" in line):
            ji["maxpoints"] = line.split(':')[1].strip()
        si = scheduleInfo(jobname)
        ji["rundays"] = si["rundays"]
        ji["runat"] = si["runat"]
    return ji


def scheduleInfo(jobname):
    rc, stdout, stderr = cmd(["veeamconfig", "schedule", "show", "--jobName", jobname])
    si = {}
    for line in to_text(stdout).split('\n'):
        if ("Every day" in line):
            si["rundays"] = "All"
        if ("Days" in line):
            si["rundays"] = line.split(':')[1].strip()
        if ("At" in line):
            si["runat"] = line.split(':', 1)[1].strip()
    return si


def main():
    module_args = dict(
        type=dict(type='str', required=True, choices=['job', 'list']),
        state=dict(type='str', required=False, choices=['absent', 'present']),
        prefreeze=dict(type='path', required=False),
        includedirs=dict(type='path', required=False),
        name=dict(type='str', required=False),
        reponame=dict(type='str', required=False),
        maxpoints=dict(type='str', required=False),
        rundays=dict(type='str', required=False),
        runat=dict(type='str', required=False)
    )
    required_if_args = [
        ['type', 'job', ['name', 'state']],
        ['state', 'present', ['includedirs', 'reponame']]
    ]
    required_together_args=[
        [ 'rundays', 'runat' ]
    ]
    result = dict(
        changed=False,
    )
    module = AnsibleModule(
        argument_spec=module_args,
        required_if=required_if_args,
        required_together=required_together_args,
        supports_check_mode=True
    )
    if module.check_mode:
        module.exit_json(**result)

    if module.params['type'] == 'list':
        rc, stdout, stderr = cmd(["veeamconfig", "job", "list"])
        if rc == 0:
            result['jobs'] = []
            for str in to_text(stdout).split('\n')[1:-1]:
                result['jobs'].append(str.split()[0])
        else:
            module.fail_json(msg=json.dumps(to_text(stderr)), **result)

    if module.params['type'] == 'job':
        if module.params['state'] == 'present':
            cmd_txt = ["veeamconfig", "job", "create", "fileLevel", "--name", module.params['name'], "--includeDirs", module.params['includedirs'], "--repoName", module.params['reponame']]
            if module.params['prefreeze'] != None:
                cmd_txt.append("--prefreeze")
                cmd_txt.append(module.params['prefreeze'])
            if module.params['maxpoints'] != None:
                cmd_txt.append("--maxPoints")
                cmd_txt.append(module.params['maxpoints'])
            if module.params['rundays'] != None:
                if module.params['rundays'].lower() == "all":
                    cmd_txt.append("--daily")
                else:
                    cmd_txt.append("--weekdays")
                    cmd_txt.append(module.params['rundays'])
            if module.params['runat'] != None:
                cmd_txt.append("--at")
                cmd_txt.append(module.params['runat'])
        else:
            cmd_txt = ["veeamconfig", "job", "delete", "--name", module.params['name']]
        rc, stdout, stderr = cmd(cmd_txt)
        if rc == 0:
            result['message'] = json.dumps(to_text(stdout).split('\n')[0])
            result['changed'] = True
        else:
            if ("already exists" in to_text(stderr).split('\n')[0]):
                ji = jobInfo(module.params['name'])
                for key in ji:
                    if ji[key].lower().replace(' ', '') != module.params[key].lower().replace(' ', ''):
                        if key in ["rundays", "runat"]:
                            cmd_txt = ["veeamconfig", "schedule", "set", "--jobName", module.params['name']]
                            if module.params['rundays'] != None:
                                if module.params['rundays'].lower() == "all":
                                    cmd_txt.append("--daily")
                                else:
                                    cmd_txt.append("--weekdays")
                                    cmd_txt.append(module.params['rundays'])
                            if module.params['runat'] != None:
                                cmd_txt.append("--at")
                                cmd_txt.append(module.params['runat'])
                        else:
                            cmd_txt = ["veeamconfig", "job", "edit", "fileLevel", "--includeDirs", module.params['includedirs'], "--repoName", module.params['reponame']]
                            if module.params['prefreeze'] != None:
                                cmd_txt.append("--prefreeze")
                                cmd_txt.append(module.params['prefreeze'])
                            if module.params['maxpoints'] != None:
                                cmd_txt.append("--maxPoints")
                                cmd_txt.append(module.params['maxpoints'])
                            cmd_txt.append("for")
                            cmd_txt.append("--name")
                            cmd_txt.append(module.params['name'])
                        rc, stdout, stderr = cmd(cmd_txt)
                        if rc == 0:
                            result['changed'] = True
                            result['message'] = json.dumps(to_text(stdout).split('\n')[0])
                        else:
                            result['message'] = json.dumps(to_text(stderr).split('\n')[0])
                        break
                    else:
                        result['message'] = json.dumps(to_text(stderr).split('\n')[0])
            else:
                module.fail_json(msg=json.dumps(to_text(stderr).split('\n')[0]), **result)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
