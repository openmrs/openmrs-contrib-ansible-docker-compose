#!/usr/bin/env python3

# Auto-generates docs from conf file
# Requires OpenMRSBot.conf in current working directory
from jinja2 import Template
import re

ALIAS_IDENTIFIER = 'supybot.plugins.Alias.aliases.'
LOCKING_IDENTIFIER = '.locked'
HERALD_IDENTIFIER = 'supybot.plugins.Herald.default: '
PLUGIN_REGEX = '^supybot.plugins.[a-zA-Z0-9_]*: True$'

def loadAliases(conf):
    ret = ''

    for line in conf.split('\n'):
        if line.startswith(ALIAS_IDENTIFIER) and LOCKING_IDENTIFIER not in line:
            ret += '- {}\n'.format(line[len(ALIAS_IDENTIFIER):])

    return ret

def loadHeraldMessage(conf):
    for line in conf.split('\n'):
        if line.startswith(HERALD_IDENTIFIER):
            return line[len(HERALD_IDENTIFIER):]
    else:
        return ''

def loadPlugins(conf):
    prog = re.compile(PLUGIN_REGEX)
    ret = ''

    for line in conf.split('\n'):
        if prog.match(line):
            ret += '- {}\n'.format(line[len('supybot.plugins.'):line.index(':')])

    return ret


template_str = ''
conf = ''

with open('README.jinja', 'r') as f:
    for line in f.readlines():
        template_str += line

with open('OpenMRSBot.conf', 'r') as f:
    for line in f.readlines():
        if not line.startswith('#'):  # No comments
            conf += line

template = Template(template_str)
docs_compiled = template.render(
    aliaslist=loadAliases(conf),
    heraldmessage=loadHeraldMessage(conf),
    pluginlist=loadPlugins(conf)
)

with open('README.md', 'w') as f:
    f.write(docs_compiled)


