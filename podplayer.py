#!/usr/bin/python3

import argparse
import sqlite3
import xml.etree.ElementTree as ET
import urllib.request
import re
import time
from subprocess import call

class ImNotDoingThat (Exception):
    pass #Legit pass; this is not a stub.

class Podcast (object):

    urlre = re.compile ("(^http.*?)\?")

    def __init__(self, podcast_id=None, podcast_priority=None,
                 podcast_load_type=None, podcast_url=None, podcast_name=None,
                 podcast_last_played=None, verbose=False, debug=False):

        self.verbose             = verbose or debug
        self.debug               = debug

        self.podcast_id          = podcast_id
        self.podcast_priority    = podcast_priority
        self.podcast_load_type   = podcast_load_type
        self.podcast_url         = podcast_url
        self.podcast_name        = podcast_name
        self.podcast_last_played = podcast_last_played

        self.episode_list        = None

    def make_selection(self):
        if self.verbose:
            if self.podcast_name is None:
                usename = self.podcast_url
            else:
                usename = self.podcast_name
            print ("Checking %s for new content." % (usename,))
        if self.episode_list is None:
            self.get_episode_list()

        if len(self.episode_list) == 0:
            return None

        if self.debug:
            for episode in self.episode_list:
                print("   ", episode)
            print (self.podcast_last_played)
        
        if self.podcast_last_played == self.episode_list[0]:
            if self.debug:
                print("I select none of these becasue the most recent episode has been played.")
            return None
        
        
        if self.podcast_load_type == 'front':
            episode_url = self.episode_list[0]
            if self.debug:
                print("I select %s, which is the newest episode." % (episode_url,))
        else:
            if self.podcast_last_played in self.episode_list:
                done = False
                for episode in self.episode_list:
                    if episode == self.podcast_last_played:
                        done = True
                    elif not done:
                        episode_url = episode
            else:
                episode_url = self.episode_list[-1]

        if episode_url is None:
            return None
        else:
            return Selection(podcast=self, episode_url=episode_url, verbose=self.verbose, debug=self.debug)

    def retrieve_feed_text(self):
        with urllib.request.urlopen(self.podcast_url, None, 5) as infile:
            return infile.read()
        
        
    def get_episode_list(self):
        #Retrieve the feed and parse it
        tree = ET.fromstring(self.retrieve_feed_text())

        #Get channel name
        self.podcast_name = tree.findall('channel')[0].findall('title')[0].text
        
        #Get the enclosures out of each and put them on a list.
        self.episode_list = []
        for channel in tree.findall('channel'):
            for item in channel.findall('item'):
                for enclosure in item.findall('enclosure'):
                    given_url = enclosure.attrib['url']
                    urlmatch = self.urlre.match(given_url)
                    if urlmatch:
                        episode_url = urlmatch.group(1)
                    else:
                        episode_url = given_url
                    self.episode_list += [episode_url]

class Selection (object):
    def __init__(self, podcast=Podcast(), episode_url=None, verbose=False, debug=False):
        self.verbose     = verbose or debug
        self.debug       = debug
        self.podcast     = podcast
        self.episode_url = episode_url

        self.podcast.verbose = self.verbose
        self.podcast.debug   = self.debug

class PodPlayerDB(object):

    init_if_needed_steps = [
        "CREATE TABLE IF NOT EXISTS podcast_v1 (podcast_id INTEGER PRIMARY KEY AUTOINCREMENT, podcast_priority INTEGER DEFAULT 10, podcast_load_type TEXT DEFAULT 'back', podcast_url TEXT, podcast_name TEXT, podcast_last_played TEXT)",
        "CREATE INDEX IF NOT EXISTS podcast_v1_priority ON podcast_v1(podcast_priority)",
        "CREATE INDEX IF NOT EXISTS podcast_v1_url ON podcast_v1(podcast_url)"
    ]

    destroy_steps = [
        "DROP INDEX IF EXISTS podcast_v1_url",
        "DROP INDEX IF EXISTS podcast_v1_priority",
        "DROP TABLE IF EXISTS podcast_v1"
    ]

    exists_podcast_select = "SELECT count(0) FROM podcast_v1 WHERE podcast_url = ?"

    add_podcast_insert = "INSERT INTO podcast_v1 (podcast_url, podcast_load_type, podcast_priority) values (?,?,?)" 

    remove_podcast_delete = "DELETE FROM podcast_v1 WHERE podcast_url = ?"

    update_last_played_update = "UPDATE podcast_v1 SET podcast_last_played = ? WHERE podcast_URL =?"

    update_name_update = "UPDATE podcast_v1 SET podcast_name = ? WHERE podcast_URL =?"

    scan_podcasts_select = "SELECT podcast_id, podcast_priority, podcast_load_type, podcast_url, podcast_name, podcast_last_played FROM podcast_v1 ORDER BY podcast_priority ASC"
    
    def __init__(self, dbpath, verbose=False, debug=False):
        self.verbose  = verbose or debug
        self.debug    = debug

        self.dbpath   = dbpath
        self.dbi      = sqlite3.connect(self.dbpath)

        self.init_if_needed()

    def init_if_needed(self):
        self.run_steps(self.init_if_needed_steps)
        self.dbi.commit()

    def destroy(self):
        self.run_steps(self.destroy_steps)
        self.dbi.commit()
        
    def run_steps(self, steps):
        if type(steps) is str:
            steps = [steps]
        cursor = self.dbi.cursor()
        for step in steps:
            cursor.execute(step)

    def exists_podcast(self, podcast_url):
        cursor = self.dbi.cursor()
        cursor.execute(self.exists_podcast_select, (podcast_url,))
        result = cursor.fetchone()
        if result[0] == 0:
            return False
        return True

    def add_podcast(self, podcast_url, podcast_priority, podcast_type):
        cursor = self.dbi.cursor()
        cursor.execute(self.add_podcast_insert, (podcast_url, podcast_type, podcast_priority))
        self.dbi.commit()

    def remove_podcast(self, podcast_url):
        cursor = self.dbi.cursor()
        cursor.execute(self.remove_podcast_delete, (podcast_url,))
        self.dbi.commit()
        
    def update_last_played(self, podcast_url, episode_url):
        cursor = self.dbi.cursor()
        cursor.execute(self.update_last_played_update, (episode_url, podcast_url))
        self.dbi.commit()

    def update_name(self, podcast_url, podcast_name):
        cursor = self.dbi.cursor()
        cursor.execute(self.update_name_update, (podcast_name, podcast_url))
        self.dbi.commit()
        
    def scan_podcasts(self):
        cursor = self.dbi.cursor()
        cursor.execute(self.scan_podcasts_select)
        for result in cursor:
            #0 podcast_id
            #1 podcast_priority
            #2 podcast_load_type
            #3 podcast_url
            #4 podcast_name
            #5 podcast_last_played
            yield Podcast(podcast_id=result[0], podcast_priority=result[1], podcast_load_type=result[2], podcast_url=result[3], podcast_name=result[4], podcast_last_played=result[5], verbose=self.verbose, debug=self.debug)  
        
class PodPlayer(object):
    def __init__(self, dbpath, verbose=False, debug=False):
        self.verbose  = verbose or debug
        self.debug    = debug

        self.dbpath   = dbpath
        self.database = PodPlayerDB(dbpath=self.dbpath, verbose=self.verbose, debug=self.debug)

    def add_podcasts(self, url_list, podcast_priority, podcast_type):
        for podcast_url in url_list:
            if self.database.exists_podcast(podcast_url):
                print("Warning:  Skipping %s becasue it is already in the database." % (podcast_url,))
            else:
                self.database.add_podcast(podcast_url=podcast_url, podcast_priority=podcast_priority, podcast_type=podcast_type)

    def remove_podcasts(self, url_list):
        for podcast_url in url_list:
            if self.database.exists_podcast(podcast_url):
                self.database.remove_podcast(podcast_url)
            else:
                print("Warning:  Skipping %s becasue it is not in the database." % (podcast_url,))

    def pretty_list(self):
        print ("%-3s %-5s %-30s %s" % ("Pri","Type","Name","URL"))
        print ("=" * 80)
        for entry in self.database.scan_podcasts():
            print ("%3d %-5s %-30s %s" % (entry.podcast_priority, entry.podcast_load_type, entry.podcast_name, entry.podcast_url))

    def make_selection(self):
        selection = None
        for podcast in self.database.scan_podcasts():
            selection = podcast.make_selection()
            if selection is not None:
                return selection

    def launch_player(self, selection):
        call(["/usr/bin/wget", "-O", "/dev/shm/podplayer.mp3", selection.episode_url])
        call(["/usr/bin/mplayer", "/dev/shm/podplayer.mp3"])

    def update_last_played(self, selection):
        self.database.update_last_played(selection.podcast.podcast_url, selection.episode_url)

    def update_podcast_name(self, podcast):
        self.database.update_name(podcast.podcast_url, podcast.podcast_name)
        
    def play_one(self):
        selection = self.make_selection()
        if selection is not None:
            self.update_podcast_name(selection.podcast)
            self.launch_player(selection)
            self.update_last_played(selection)
            return True
        return False

    def play_continuous(self):
        while True:
            if not self.play_one():
                print ("Waiting until next quarter-hour.")
                time.sleep(900.0 - time.time() % 900.0)
        
            
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose",    help="Verbose output",                action="store_true")
    parser.add_argument("-D", "--debug",      help="Debugging output",              action="store_true")
    parser.add_argument("-d", "--dbpath",     help="Path to database", type=str, default="podplayer.db")
    parser.add_argument("-a", "--add",        help="Add podcasts",                  action="store_true")
    parser.add_argument("-t", "--type",       help="Load type",      type=str, choices=['front','back'])
    parser.add_argument("-p", "--priority",   help="Priority",                     type=int, default=10)
    parser.add_argument("-r", "--remove",     help="Remove podcasts",               action="store_true")
    parser.add_argument("-l", "--list",       help="List podcasts",                 action="store_true")
    parser.add_argument("-P", "--play",       help="Play podcast",                  action="store_true")
    parser.add_argument("-c", "--continuous", help="Play podcasts continuously",    action="store_true")
    parser.add_argument("arguments",          help="Arguments if appropriate",      type=str, nargs="*")
    args = parser.parse_args()

    verbose = args.verbose or args.debug
    debug   = args.debug

    if args.add and args.remove:
        raise ImNotDoingThat("--add and --remove are mutually exclusive.")

    if debug:
        print ("verbose",   args.verbose)
        print ("debug",     args.debug)
        print ("dbpath",    args.dbpath)
        print ("add",       args.add)
        print ("type",      args.type)
        print ("priority",  args.priority)
        print ("remove",    args.remove)
        print ("list",      args.list)
        print ("play",      args.play)
        print ("continuous",args.continuous)
        print ("arguments", args.arguments)
    
    podplayer  = PodPlayer(dbpath=args.dbpath, verbose=verbose, debug=debug)
    verb_found = False
    
    if args.add:
        podplayer.add_podcasts(args.arguments, args.priority, args.type)
        verb_found = True
    if args.remove:
        podplayer.remove_podcasts(args.arguments)
        verb_found = True
    if args.list:
        podplayer.pretty_list()
        verb_found = True
    if args.play:
        podplayer.play_one()
        verb_found = True
    if args.continuous:
        podplayer.play_continuous()
        verb_found = True
    if not verb_found:
        podplayer.play_continuous() #This sets up the default behavior.
    
if __name__ == "__main__":
    main()
    
