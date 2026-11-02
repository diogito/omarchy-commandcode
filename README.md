# Command Code usage for Omarchy

A bar widget for [Omarchy](https://omarchy.org/). It shows the same three meters as the Command Code usage page: the 5-hour window, the weekly window, and the monthly pool, with the plan name and when each one resets.

The icon is ⌘. Click it to open the panel. The labels are in English, like the other Omarchy bar panels.

## What you need

- Omarchy, with the `omarchy` command.
- A Command Code account. The panel asks for an API key the first time you open it, unless this computer is already signed in.
- Nothing else to install. The widget uses `/usr/bin/python3` from the standard library. There is no pip package.

## Install

1. Add the plugin. Omarchy asks you to confirm the clone, then which side of the bar to use. Right is already selected.

```bash
omarchy plugin add https://github.com/diogito/omarchy-commandcode.git --enable
```

The plugin id is `commandcode.usage`.

2. Click the ⌘ icon.

If `cmd login`, Pi, omp, or OpenCode already has a Command Code key, the meters show up and there is nothing else to configure.

Otherwise the panel opens on Setup:

- Choose **Open Studio**, or go to [commandcode.ai/studio](https://commandcode.ai/studio/).
- Generate an API key.
- Paste it into the panel and choose **Save key**.

The key is saved as `~/.commandcode/auth.json` with permissions `600`. The directory is `700`. It is not written into the bar settings, not printed, and not sent anywhere except `api.commandcode.ai`.

The same step from a terminal, if you prefer not to paste into the panel:

```bash
python3 ~/.config/omarchy/plugins/commandcode.usage/configure.py
```

`configure.py` hides the key while you type. Run it with `--replace` to save a different one later.

3. After **Save key**, the meters replace the form. Left click opens and closes the panel. Middle click, or `r` while it is open, refreshes now.

Move the icon later:

```bash
omarchy bar move commandcode.usage --section right
```

`left` and `center` work the same way.

If that id is already installed from a copied folder, remove the old copy and add this repo. `omarchy plugin update` only works for a plugin Omarchy cloned from git.

```bash
omarchy plugin remove commandcode.usage
omarchy plugin add https://github.com/diogito/omarchy-commandcode.git --enable
```

## Where it finds the account

The widget looks for a key in this order. Pasting into the panel writes item 4. An environment variable still wins, because that is how the Command Code CLI works:

1. `COMMAND_CODE_API_KEY`
2. `COMMANDCODE_API_KEY`
3. `CMD_API_KEY`
4. `~/.commandcode/auth.json` from `cmd login`
5. Pi (`~/.pi/agent/auth.json`) or omp (`~/.omp/agent/auth.json`)
6. OpenCode (`~/.local/share/opencode/auth.json` or `~/.config/opencode/auth.json`)

`cmd login` writes the same `~/.commandcode/auth.json` file, so doing that instead of pasting is enough.

The key is sent only to `api.commandcode.ai`. It is not written into the panel, the shell config, or the log.

A rejected key was replaced or revoked. Paste a new one, or run `cmd login` again.

The environment variable has to be present in the Omarchy shell process. A key exported only in a terminal profile is invisible to the bar, and while it is set the panel cannot override it by saving a file. `cmd login` or the paste field avoids that.

## Using it

- Left click opens and closes the panel.
- Middle click, or `r` while the panel is open, refreshes now.
- The meters also refresh on their own. The default is every 5 minutes.

```bash
omarchy bar set commandcode.usage refreshIntervalSec 120 --json
```

`refreshIntervalSec` is seconds, from 60 to 3600. Pass `--json` so the value is stored as a number.

From a terminal, the same panel can be opened with `omarchy-shell commandcode.usage open`. On a bar that is drawn once per monitor, that command opens the panel on the monitor that registered first.

## Update and remove

```bash
omarchy plugin update commandcode.usage
omarchy plugin disable commandcode.usage
omarchy plugin remove commandcode.usage
```

## What the monthly meter means

Command Code reports used and cap for the 5-hour and weekly windows. It does not report a monthly cap. The monthly percentage is the spend in the current billing period divided by that spend plus the monthly credits still remaining, and the date is the end of the billing period. That is the same pair of numbers the usage page shows.

The requests go to the usage endpoints the Command Code CLI uses. They are not a versioned public API. If Command Code changes them, the panel shows an error instead of a made-up percentage.

## Checks

From this directory, with no network and no API key:

```bash
python3 test_usage.py
omarchy plugin validate .
```

## License

MIT. See [LICENSE](LICENSE).
