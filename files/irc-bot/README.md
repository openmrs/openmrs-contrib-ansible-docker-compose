# OpenMRS IRC Bot


## Aliases

Aliases are commands used to interact with OpenMRSBot. Some commands take arguments. Arguments are documented with symbols $1 $2 $3 etc. for arguments 1, 2, 3, etc. Users can invoke a command in the IRC channel with the `!` symbol. Example (use the google alias to return a url to the google search for keyword openmrs): `!google openmrs`

- jira: reply [web title https://tickets.openmrs.org/browse/$1] - https://tickets.openmrs.org/browse/$1
- codereview: reply Code review $1 is at https://source.openmrs.org/cru/$1
- test2: reply [web title https://tickets.openmrs.org/browse/$1] - https://tickets.openmrs.org/browse/$1
- changeset: reply Details of changeset $1 should be available at http://source.openmrs.org/qsearch?q=$1
- facts: factoids search *
- google: reply http://www.google.com/search?q=$1
- beer2: private here's a beer
- cs: reply Details of changeset $1 should be available at http://source.openmrs.org/qsearch?q=$1
- cr: reply Code review $1 is at https://source.openmrs.org/cru/$1
- dcme: action slides $1 a litre of coke light
- scrumon: action says the DAILY SCRUM MEETING is STARTING. This meeting should not last longer than 15 minutes. Please hold other comments until the end of the meeting, or message someone privately. Thank you! ScrumMaster @1- you may begin when ready.
- review: reply Code review $1 is at https://source.openmrs.org/cru/$1
- beer: action slides $1 a pint
- cokeme: action Drugs are bad
- test: web title https://issues.openmrs.org/$1
- define: reply [web title http://dictionary.reference.com/browse/$1] - http://dictionary.reference.com/browse/$1
- googledefine: reply http://www.google.com/search?q=define%3A+$1
- beerme: action slides $1 a pint
- holidays: echo OpenMRS Holidays for 2015: Jan 1, Jan 19, Feb 16, May 25, Jul 3, Sep 7, Oct 12, Nov 11, Nov 26, Dec 25 - https://wiki.openmrs.org/x/lIHKB
- hi: action offers this IRC tip: Rather than just saying Hi at people, it's more effective (and less rude) if you just ask your question in the channel. That way the person you want (or others) can answer as soon as they see your question, rather than waiting on you to look at your screen again. :-)
- scrumoff: action says the DAILY SCRUM MEETING has ENDED. This channel is now returned to normal hacking operations. Post-scrum meeting follow-up conversations may now begin.
- ticket: reply [web title https://tickets.openmrs.org/browse/$1] - https://tickets.openmrs.org/browse/$1
- psu: PSU: Please ask your questions on talk.openmrs.org and ask your class mates to do the same.
- mailinglist: devlist $*
- powerup: action slides $1 a Jack and Coke
- requestsvnspace: More information on the OpenMRS code repository and on how to request access is available at: http://wiki.openmrs.org/display/docs/Code+Repository
- refer: action refers $1 to $2


## Plugins

The following pugins are enabled in OpenMRSBot:

- Admin
- Alias
- AutoMode
- Channel
- ChannelLogger
- ChannelStats
- Config
- Factoids
- Herald
- Karma
- MeetBot
- Misc
- NickCapture
- Owner
- RSS
- Reply
- Seen
- Services
- ShrinkUrl
- Status
- User
- Web
- alwaysLoadImportant


## Known Issues

- Meetbot seems to be unsupported in Limnoria
- GPG functionality is unavailable