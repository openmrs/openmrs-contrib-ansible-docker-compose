#!/usr/bin/env python3

# Auto-generates docs from conf file
# Requires OpenMRSBot.conf in current working directory
from jinja2 import Template

ALIAS_IDENTIFIER = 'supybot.plugins.Alias.aliases.'
LOCKING_IDENTIFIER = '.locked'

def loadAliases():
    ret = ''

    with open('OpenMRSBot.conf', 'r') as f_config:
        for line in f_config.readlines():
            if line.startswith(ALIAS_IDENTIFIER) and LOCKING_IDENTIFIER not in line:
                ret += '- {}'.format(line[len(ALIAS_IDENTIFIER):])

    return ret


template_str = ''
with open('README.jinja', 'r') as f:
    for line in f.readlines():
        template_str += line

template = Template(template_str)
docs_compiled = template.render(
    aliaslist=loadAliases()
)

with open('README.md', 'w') as f:
    f.write(docs_compiled)


