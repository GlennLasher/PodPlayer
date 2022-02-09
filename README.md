# PodPlayer

Minimalist, priority-based podcatcher

## What is special about this?

This podcatcher addresses a specific problem I have with podcatchers.  They tend to download a lot of things that I never listen to, for instance, downloading a news podcast every hour.

This podcatcher solves the problem by allowing me to set a priority for each podcast, as well as to indicate whether or not I want to keep or toss the backlog.

## Prerequisites

You will need the mplayer media player installed at /usr/bin/mplayer and wget installed at /usr/bin/wget.  There is a TODO item to make this configurable at a future date.

## Synopsis
        
    usage: podplayer.py [-h] [-v] [-D] [-d DBPATH] [-a] [-t {front,back}] [-p PRIORITY] [-r]
                        [-l] [-P] [-c]
                        [arguments [arguments ...]]
    
    positional arguments:
      arguments             Arguments if appropriate
    
    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         Verbose output
      -D, --debug           Debugging output
      -d DBPATH, --dbpath DBPATH
                            Path to database
      -a, --add             Add podcasts
      -t {front,back}, --type {front,back}
                            Load type
      -p PRIORITY, --priority PRIORITY
                            Priority
      -r, --remove          Remove podcasts
      -l, --list            List podcasts
      -P, --play            Play podcast
      -c, --continuous      Play podcasts continuously

## Use

For starters, you will want to create your database.  By default, the database will go at podplayer.db in the current directory.  You can make it go someplace else by invoking the -d option.  Simply invoking the script will create the database.

Get the URL for the RSS feed for your podcast of interest.  Add it to the database like this:

    ./podplayer.py -p {priority} -t {type} -a [URL [URL [ . . . ] ] ]

For instance, to add the NPR News Now podcast as a front-loaded at priority 10, do this:

    ./podplayer.py -p 10 -t front -a https://feeds.npr.org/500005/podcast.xml

To remove one or more podcasts, use the -r option:

    ./podplayer.py -r [URL [URL [ . . . ] ] ]

For instance, to remove the NPR News Now podcast, do this:

    ./podplayer.py -r https://feeds.npr.org/500005/podcast.xml

To see a list of podcasts, use the -l option:

    ./podplayer.py -l

To play just one podcast, use the -P option:

    ./podplayer.py -P

To play continuously, you can either use the -c option, or no options:

    ./podplayer.py

