# Home Lab Environment

## Workstations
- **Main PC:** Linux Mint Debian Edition 7 (LMDE 7)
- **Laptop:** Linux Mint Debian Edition 7 (LMDE 7)
- **Sugey's Laptop:** Windows 11 (Lenovo)

## Network Services
- **DNS/DHCP:** dnsmasq (192.168.1.10, config: `/etc/dnsmasq.d/dnsmasq.conf`)
- **Domain:** lan
- **SSH alias:** `ssh lap` → 192.168.1.11

## Active Services
- **Home Automation:** Home Assistant (192.168.1.3, VM via VirtualBox)
  - **Auto-start:** systemd user service at `~/.config/systemd/user/homeassistant-vm.service`
  - Graceful shutdown via ACPI power button on boot/shutdown
  - Run `systemctl --user enable homeassistant-vm.service` to activate (enabled)
- **Development Workloads:** NavIntel environment prototyping; neural network library development (feed-forward and backpropagation testing).

## Virtual Machines
- **Home Assistant VM:** VirtualBox VM running Home Assistant
  - Config path: `/mnt/ha_config/`
  - Management: `~/bin/ha_cmd.sh`