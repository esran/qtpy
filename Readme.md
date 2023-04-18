# qtpy

Scrappy little python utility for performing some operations on qbittorrent server.

 * Force a reannounce for any torrent without a listed tracker.
 * Pause in progress torrents if they would fill the disk.
 * [optional] Resume incomplete torrents if there is space available.
 * [optional] Add tags based on tracker info

## usage

You will need a config file. An example is provided `config-example.json`. With this
in place simply run with the following command:

```
	/path/to/qt.py --config=/path/to/config.json
```

The autoresume is off by default but can be enabled by including the additional flag:

```
	--auto-resume
```

This can also be set in the config file.

## cron

You will probably want to run this from cron. Something like the following which will
also capture any stderr to a file (rather than have cron email you).

```
*/1 * * * * /path/to/qt.py 2> /path/to/logs/qtpy.log
```

This runs every minute, which is useful for the force reannounce. If that isn't of
interest to you then tweak the cron set up accordingly.
