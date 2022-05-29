#!/usr/bin/python3

import argparse
import sqlite3
import xml.etree.ElementTree as ET
import urllib.request
import re
import time
from subprocess import call

class ImNotDoingThat (Exception):
    pass

class Podcast (object):

    """Class Podcast is a data structure representing a podcast feed, with
    methods needed to fetch the feed, parse it, and make a decision on
    what needs played.

    """
    
    #urlre is a regular expression that strips off the query portion
    #of the URL, both as a privacy measure and as a way to ensure that
    #URLs match.
    urlre = re.compile ("(^http.*?)\?")

    def __init__(self, podcast_id=None, podcast_priority=None,
                 podcast_load_type=None, podcast_url=None, podcast_name=None,
                 podcast_last_played=None, verbose=False, debug=False):

        """Podcast.__init__() mostly copies its parameters to like-named
        properties in the instance.  It also initializes the
        self.episode_list property to None.

        """
        
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
        """Podcast.make_selection() calls get_episode_list() (if needed) and
        then decides what to play.  The selection process is as follows:

        If there are no episodes, there's nothing to play.  Return
        None.
        
        If the most recent episode is also the last play, there's
        nothing to play.  Return None.

        If we haven't returned anything yet and this is a front-loaded
        podcast, select the most recent episode and return a Selection
        object with that.

        OTOH, if it is a rear-loaded one, find the episode after the
        most-recent played, and return a Selection object with that.

        """

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
                #There has to be a better way to do this.  I hate
                #using loop flags, but this works for now.
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
        """Podcast.retrieve_feed_text() retrieves the XML from the podcast
        feed and returns it.

        """

        #TODO:  Make the timeout configurable.
        try:
            with urllib.request.urlopen(self.podcast_url, None, 5) as infile:
                return infile.read()
        except:
            if self.verbose:
                print ("    Download failed.  Trying next feed.")
            return None
            
        
    def get_episode_list(self):
        """Podcast.get_episode_list() parses the podcast XML and boils it
        down to just the enclosure URLs.

        """

        #TODO: Insert a sort step here.  We are relying on the podcast
        #generator to produce a feed in reverse-chronological order,
        #and that might not be a valid assumption.
        
        #Retrieve the feed.
        treetext = self.retrieve_feed_text()

        #Determine if we got anything
        if treetext is None:
            #It's empty.  Say so.
            self.episode_list = []
        else:
            #Figure out what we got.
            tree = ET.fromstring(treetext)
        
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
    """Class Selection is simply a data structure, nothing else.  It
    carries the URL of a selection, and the Podcast object that
    produced the selection.

    """


    def __init__(self, podcast=Podcast(), episode_url=None, verbose=False, debug=False):
        """Selection.__init__() pretty much just copies arguments to
        like-named properties, and further transfers verbose and debug
        flags into any included Podcast object.

        """
        
        #TODO: Figure out better default logic for the podcast
        #variable.  Actually, does it need to be defaulted?
        
        self.verbose     = verbose or debug
        self.debug       = debug
        self.podcast     = podcast
        self.episode_url = episode_url

        self.podcast.verbose = self.verbose
        self.podcast.debug   = self.debug

class PodPlayerDB(object):
    """
    Class PodPlayerDB abstracts the SQLite3 database.  
    """

    #SQL statements used by PodPlayerDB are all set up here so as to
    #keep them from cluttering up the methods.

    #Create database objects, unless they already exist.
    init_if_needed_steps = [
        "CREATE TABLE IF NOT EXISTS podcast_v1 (podcast_id INTEGER PRIMARY KEY AUTOINCREMENT, podcast_priority INTEGER DEFAULT 10, podcast_load_type TEXT DEFAULT 'back', podcast_url TEXT, podcast_name TEXT, podcast_last_played TEXT)",
        "CREATE INDEX IF NOT EXISTS podcast_v1_priority ON podcast_v1(podcast_priority)",
        "CREATE INDEX IF NOT EXISTS podcast_v1_url ON podcast_v1(podcast_url)"
    ]

    #Drop database objects, if they exist.
    destroy_steps = [
        "DROP INDEX IF EXISTS podcast_v1_url",
        "DROP INDEX IF EXISTS podcast_v1_priority",
        "DROP TABLE IF EXISTS podcast_v1"
    ]

    #Count number of instances of a given URL in the podcast_url column.
    exists_podcast_select = "SELECT count(0) FROM podcast_v1 WHERE podcast_url = ?"

    #Insert a podcast.  Don't insert a name at this time, just a url, type and priority.
    add_podcast_insert = "INSERT INTO podcast_v1 (podcast_url, podcast_load_type, podcast_priority) values (?,?,?)" 

    #Remove a podcast by URL.
    remove_podcast_delete = "DELETE FROM podcast_v1 WHERE podcast_url = ?"

    #Update the podcast_last_played column for a given podcast.
    update_last_played_update = "UPDATE podcast_v1 SET podcast_last_played = ? WHERE podcast_URL =?"

    #Update the podcast_name column for a given podcast
    update_name_update = "UPDATE podcast_v1 SET podcast_name = ? WHERE podcast_url =?"

    #Retrieve a list of podcasts in order by priority
    scan_podcasts_select = "SELECT podcast_id, podcast_priority, podcast_load_type, podcast_url, podcast_name, podcast_last_played FROM podcast_v1 ORDER BY podcast_priority ASC"
    
    def __init__(self, dbpath, verbose=False, debug=False):
        """PodPlayerDB.__init__(), in addition to copying the arguments to the
        properties, also instantiates a database connection, and calls
        init_if_needed() to set up the database.

        """
        self.verbose  = verbose or debug
        self.debug    = debug

        self.dbpath   = dbpath
        self.dbi      = sqlite3.connect(self.dbpath)

        self.init_if_needed()

    def init_if_needed(self):
        """PodPlayerDB.init_if_needed runs the steps in
        self.init_if_needed_steps to create the table and indices
        required, but only if they do not already exist.

        """
        self.run_steps(self.init_if_needed_steps)
        self.dbi.commit()

    def destroy(self):
        """PodPlayerDB.destroy() will drop all database objects by running the
        steps in self.destroy_steps.

        """

        self.run_steps(self.destroy_steps)
        self.dbi.commit()
        
    def run_steps(self, steps):
        """PodPlayerDB.run_steps() is used by init_if_needed() and destroy()
        to execute a single SQL step in a str or a group of SQL
        statements in a list.

        """

        if type(steps) is str:
            steps = [steps]
        cursor = self.dbi.cursor()
        for step in steps:
            cursor.execute(step)

    def exists_podcast(self, podcast_url):
        """PodPlayerDB.exists_podcast() takes a podcast URL and returns True
        if it is in the database, and False if not.

        """

        cursor = self.dbi.cursor()
        cursor.execute(self.exists_podcast_select, (podcast_url,))
        result = cursor.fetchone()
        if result[0] == 0:
            return False
        return True

    def add_podcast(self, podcast_url, podcast_priority, podcast_type):
        """PodPlayerDB.add_podcast() inserts a podcast into the database.  The
        podcast_name and podcast_last_played columns will be left
        null.

        """
        
        cursor = self.dbi.cursor()
        cursor.execute(self.add_podcast_insert, (podcast_url, podcast_type, podcast_priority))
        self.dbi.commit()

    def remove_podcast(self, podcast_url):
        """PodPlayerDB.remove_podcasts() takes a podcast URL and removes the
        corresponding record from the database.

        """

        cursor = self.dbi.cursor()
        cursor.execute(self.remove_podcast_delete, (podcast_url,))
        self.dbi.commit()
        
    def update_last_played(self, podcast_url, episode_url):
        """PodPlayerDB.update_last_played takes a podcast URL and an episode
        URL and puts the episode URL on the record for the podcast
        referenced by the podcast URL.

        """
        cursor = self.dbi.cursor()
        cursor.execute(self.update_last_played_update, (episode_url, podcast_url))
        self.dbi.commit()

    def update_name(self, podcast_url, podcast_name):
        """PodPlayerDB.update_name takes the podcast URL and the podcast name,
        and puts the name on the record associated with that URL.

        """
        cursor = self.dbi.cursor()
        cursor.execute(self.update_name_update, (podcast_name, podcast_url))
        self.dbi.commit()
        
    def scan_podcasts(self):
        """PodPlayerDB.scan_podcasts retrieves from the database a list of
        podcasts, sorted in order by priority.  It yields each as a
        Podcast object.

        """

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
    """Class PodPlayer is the glue class for this program.

    """

    def __init__(self, dbpath, verbose=False, debug=False):
        """PodPlayer.__init__ takes a database path and optional feedback
        flags, and instantiates a PodPlayerDB object.

        """
        self.verbose  = verbose or debug
        self.debug    = debug

        self.dbpath   = dbpath
        self.database = PodPlayerDB(dbpath=self.dbpath, verbose=self.verbose, debug=self.debug)

    def add_podcasts(self, url_list, podcast_priority, podcast_type):
        """PodPlyer.add_podcasts() takes a list of URLs, a priority and a
        podcast type, and inserts all of the listed URLs with that
        priority and load type into the database.  Before insertion,
        it checks to see if a podcast is already there, and prints a
        warning if it is, rather than inserting it.

        """

        for podcast_url in url_list:
            if self.database.exists_podcast(podcast_url):
                print("Warning:  Skipping %s becasue it is already in the database." % (podcast_url,))
            else:
                self.database.add_podcast(podcast_url=podcast_url, podcast_priority=podcast_priority, podcast_type=podcast_type)

    def remove_podcasts(self, url_list):
        """PodPlayer.remove_podcasts() takes a list of URLs and removes from
        the database any podcasts represented by those URLs.

        """

        for podcast_url in url_list:
            if self.database.exists_podcast(podcast_url):
                self.database.remove_podcast(podcast_url)
            else:
                print("Warning:  Skipping %s becasue it is not in the database." % (podcast_url,))

    def pretty_list(self):
        """PodPlayer.pretty_list() queries the database for all podcasts and
        presents a table of them on the console.

        """

        print ("%-3s %-5s %-30s %s" % ("Pri","Type","Name","URL"))
        print ("=" * 80)
        for entry in self.database.scan_podcasts():
            print ("%3d %-5s %-30s %s" % (entry.podcast_priority, entry.podcast_load_type, entry.podcast_name, entry.podcast_url))

    def make_selection(self):
        """PodPlayer.make_selection() loops over the yield of Podcast objects
        returned by PodPlayerDB.scan_podcasts() and calls
        Podcast.make_selection on each until it finds one that returns
        a result.  If all of them return None, then it will also
        return None, otherwise it will return a Selection object
        representing its choice and the Podcast that produced that
        choice.

        """
        
        selection = None
        for podcast in self.database.scan_podcasts():
            selection = podcast.make_selection()
            if selection is not None:
                return selection

    def launch_player(self, selection):
        """PodPlayer.launch_player() takes a Selection object.  It then calls
        external programs, first wget to retrieve the content, then
        mplayer to play it.

        """

        #TODO:  Make the path where the downloaded file goes into a configurable.

        #TODO:  Make the path to the fetcher configurable.

        #TODO:  Make the path to the media player configurable.
        
        #Design note: Yes, I could have given the URL to mplayer and
        #it would play.  The problem with doing this is that if you
        #put it on pause for a long time, the server may time out and
        #close the connection and it won't restart.  Also, some
        #servers balk at seeks.  By grabbing it into a file first, you
        #avoid that.

        #Design note: The path given of /dev/shm/podplayer.mp3 was
        #chosen because it puts the file into a RAMdisk and therefore
        #puts no needless wear on the physical hardware.

        #Design note: Yes, I could have used urllib to get the
        #content.  Can't think of a reason to go to the effort,
        #though, given that we're just going to write the content to a
        #file unchanged.

        call(["/usr/bin/wget", "--timeout=5", "-O", "/dev/shm/podplayer.mp3", selection.episode_url])
        call(["/usr/bin/mplayer", "/dev/shm/podplayer.mp3"])

    def update_last_played(self, selection):
        """PodPlayer.update_last_played() takes a selection object and updates
        the record for the podcast in the database with the selected
        podcast.  It does this by calling
        PodPlayerDB.update_last_played() with the relevant properties
        extracted.

        """

        self.database.update_last_played(selection.podcast.podcast_url, selection.episode_url)

    def update_podcast_name(self, podcast):
        """PodPlayer.update_podcast_name() takes a podcast object and updates
        the database record for it with the podcast name.  It does
        this by calling PodPlayerDB.update_podcast_name() with the
        relevant properties extracted.

        """
        self.database.update_name(podcast.podcast_url, podcast.podcast_name)
        
    def play_one(self):
        """PodPlayer.play_one() steps through the podcast selection process
        and then, if successful, starts playback and updates the
        database to indicate that the playback happened.  It returns
        True if it was able to find something to play, and False if
        not.

        """
        selection = self.make_selection()
        if selection is not None:
            self.update_podcast_name(selection.podcast)
            self.launch_player(selection)
            self.update_last_played(selection)
            return True
        return False

    def play_continuous(self):
        """PodPlayer.play_continuous() starts an infinite loop.  It will call
        self.play_one() and if it was able to find something to play,
        it will immediately launch another one on completion.  If it
        did not find anything to play, it will sleep until the quarter
        hour.

        """

        #TODO: Make the sleep time a configurable.  Also make it
        #configurable if it is a point on the clock versus a set
        #interval.
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
    
