## PyNinja Reinstall and Service Management

This document provides commands for reinstalling PyNinja and managing its service across `macOS`, and `Linux`

### macOS

Force reinstall PyNinja to a particular version.

```shell
{
  "command": "~/pyninja/venv/bin/python -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja==3.0.0a0",
  "timeout": 300
}
```

Uninstall existing PyNinja and then force reinstall a particular version.

```shell
{
  "command": "~/pyninja/venv/bin/python -m pip uninstall --no-cache --no-cache-dir PyNinja -y && ~/pyninja/venv/bin/python -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja==3.0.0a0",
  "timeout": 300
}
```

Check existing PyNinja service name and status.

```shell
{
  "command": "launchctl list | grep pyninja",
  "timeout": 30
}
```

Restart the PyNinja service.

- `kickstart` tells launchd to stop and immediately restart the service.
- `-k` makes it kill the existing process first (force restart)
- You need to pass the full service label (e.g., system/com.example.pyninja), not just pyninja.

```shell
{
  "command": "launchctl kickstart -k gui/$(id -u)/pyninja-process",
  "timeout": 30
}
```

### Linux

Force reinstall PyNinja to a particular version.

```shell
{
  "command": "~/pyninja/venv/bin/python -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja==3.0.0a0",
  "timeout": 300
}
```

Uninstall existing PyNinja and then force reinstall a particular version.

```shell
{
  "command": "~/pyninja/venv/bin/python -m pip uninstall --no-cache --no-cache-dir PyNinja -y && ~/pyninja/venv/bin/python -m pip install --no-cache --no-cache-dir --force-reinstall PyNinja==3.0.0a0",
  "timeout": 300
}
```

Check existing PyNinja service name and status.

```shell
{
  "command": "systemctl | grep pyninja",
  "timeout": 3
}
```

Restart the PyNinja service.

```shell
{
  "command": "echo ${PASSWORD} | sudo -S systemctl restart pyninja.service",
  "timeout": 30
}
```

### Check PyNinja Version

```shell
{
  "command": "~/pyninja/venv/bin/python -m pip freeze | grep PyNinja",
  "timeout": 3
}
```
