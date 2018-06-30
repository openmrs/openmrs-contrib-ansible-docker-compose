#!/usr/bin/env python3

# Auto-generates docs from conf file
# Requires OpenMRSBot.conf in current working directory

ALIAS_IDENTIFIER = 'supybot.plugins.Alias.aliases.'
LOCKING_IDENTIFIER = '.locked'

def printAliases(f_readme):
    with open('OpenMRSBot.conf', 'r') as f_config:
        for line in f_config.readlines():
            if line.startswith(ALIAS_IDENTIFIER) and LOCKING_IDENTIFIER not in line:
                f_readme.write('- {}'.format(line[len(ALIAS_IDENTIFIER):]))


with open('README.md', 'w') as f:
    f.write('# OpenMRS IRC Bot\n\n')
    f.write('## What does OpenMRS IRC bot do?\n\n')
    f.write('### Aliases:\n\n')
    f.write(
        'Aliases are commands used to interact with OpenMRSBot.\
        Some commands take arguments.\
        Arguments are documented with symbols $1 $2 $3 etc. for arguments 1, 2, 3, etc.\
        Users can invoke a command in the IRC channel with the `!` symbol.\
        Example (use the google alias to return a url to the google search for keyword openmrs): `!google openmrs`\n\n'
    )


    printAliases(f)
