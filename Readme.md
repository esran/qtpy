= qtpy =

Scrappy little python utility for performing some operations on qbittorrent server.

 * Force a reannounce for any torrent without a listed tracker.
 * Pause in progress torrents if they would fill the disk.
 * [optional] Resume incomplete torrents if there is space available.

== usage ==

You will need a config file. An example is provided `config.json.example`. With this
in place simply run with the following command:

```
	qt.py --config=/path/to/config.json
```

The autoresume is off by default but can be enabled by including the additional flag:

```
	--auto-resume
```
