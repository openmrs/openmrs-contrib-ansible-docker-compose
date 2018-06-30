#!/usr/bin/env python3

# Auto-generates docs from conf file
# Requires OpenMRSBot.conf in current working directory
from jinja2 import Template

ALIAS_IDENTIFIER = 'supybot.plugins.Alias.aliases.'
HERALD_IDENTIFIER = 'supybot.plugins.Herald.default: '
LOCKING_IDENTIFIER = '.locked'

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

template_str = ''
conf = ''

with open('README.jinja', 'r') as f:
    for line in f.readlines():
        template_str += line

with open('OpenMRSBot.conf', 'r') as f:
    for line in f.readlines():
        conf += line

template = Template(template_str)
docs_compiled = template.render(
    aliaslist=loadAliases(conf),
    heraldmessage=loadHeraldMessage(conf)
)

with open('README.md', 'w') as f:
    f.write(docs_compiled)


