#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import signal
import random
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich import box
from datetime import datetime

console = Console()
original_mac = {}
selected_iface = None
interval = 0
running = True
log_file = "GoldMAC.log"
spoof_mode = "random"
selected_vendor = None

# Common OUIs
VENDOR_OUIS = {
    "Apple": "AC:87:A3",
    "Samsung": "F4:09:D8",
    "Intel": "3C:97:0E",
    "Cisco": "00:1A:A2",
    "VMware": "00:50:56",
    "Huawei": "00:9A:CD",
    "Dell": "FC:3F:DB",
    "Microsoft": "00:25:9C",
    "LG": "64:BC:0C",
    "Sony": "00:1E:45"
}

# ------------------ Logging ------------------ #
def log_event(message):
    with open(log_file, "a") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

# ------------------ Utility Functions ------------------ #
def check_dependency(dep):
    try:
        subprocess.run([dep, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        console.print(f"[yellow]⚠️ {dep} not found. Installing...[/yellow]")
        if os.geteuid() != 0:
            console.print("[red]❌ Please run this script with sudo/root.[/red]")
            sys.exit(1)
        subprocess.run(["apt", "install", "-y", dep])

def get_interfaces():
    try:
        output = subprocess.check_output(["ip", "-o", "link"], text=True)
        interfaces = []
        for line in output.splitlines():
            parts = line.split(":")
            if len(parts) > 1:
                iface = parts[1].strip()
                if iface != "lo":
                    interfaces.append(iface)
        return interfaces
    except Exception:
        return []

def get_mac(iface):
    try:
        return subprocess.check_output(
            ["cat", f"/sys/class/net/{iface}/address"], text=True
        ).strip()
    except Exception:
        return "??:??:??:??:??:??"

def gen_vendor_mac(vendor_oui):
    suffix = ":".join([f"{random.randint(0,255):02X}" for _ in range(3)])
    return f"{vendor_oui}:{suffix}"

def change_mac_random(iface):
    old_mac = get_mac(iface)
    subprocess.run(["ip", "link", "set", iface, "down"])

    if spoof_mode == "random":
        subprocess.run(["macchanger", "-r", iface])
    elif spoof_mode == "vendor":
        new_mac = gen_vendor_mac(VENDOR_OUIS[selected_vendor])
        subprocess.run(["macchanger", "-m", new_mac, iface])

    subprocess.run(["ip", "link", "set", iface, "up"])
    new_mac = get_mac(iface)
    log_event(f"🔀 {iface}: {old_mac} → {new_mac}")

def restore_mac(iface):
    old_mac = get_mac(iface)
    subprocess.run(["ip", "link", "set", iface, "down"])
    subprocess.run(["macchanger", "-p", iface])
    subprocess.run(["ip", "link", "set", iface, "up"])
    new_mac = get_mac(iface)
    log_event(f"♻️ Restored {iface}: {old_mac} → {new_mac}")

def handler(sig, frame):
    global running
    console.print("\n[red]⏹️ Script interrupted. Restoring MAC...[/red]")
    if selected_iface and selected_iface in original_mac:
        restore_mac(selected_iface)
        console.print(f"[green]✅ Restored MAC to {original_mac[selected_iface]}[/green]")
    running = False
    sys.exit(0)

signal.signal(signal.SIGINT, handler)

# ------------------ Main Script ------------------ #
def main():
    global selected_iface, interval, original_mac, running, spoof_mode, selected_vendor

    # ===== BANNER (COLOR ONLY MODIFIED) =====
    ascii_art = r"""
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%%%########%%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%%#*=--=------==-----=*#%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%+=-=-----=-------=--------==#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%+=-==-===+*#%%%%%%%%%%##*=---==-=+%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%+=----=*#%@@@@@@@@@@@@@@@@@@%#*=-----+%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@#==-==+#@@@@@%##*+++==+++*##%@@@@@#+=---=#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@%=====%@@@%%*==----=----------=*%%@@@%====-#@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@==-===@@@#===----+*#%%%%#*+------=*@@@+=----%@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@#=--+--==---=-+#%%@@@@@@@@@@@%#+-----==---+==*@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@*=---=--==--=%@@@@@#*****##%@@@@%+-----------+@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@#=-=----==--=%@%*+----------+*%@%=---=-------*@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@%==-=--------------=*%@@%*+--==--=---=-------%@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@+=--=----=--=----+@@@@@@@@+----==----------+@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@%--=*=-------=---#@@@@@@@@%-----------=*=--#@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@+-=#+-----------*@@@@@@@@*---------=-=#--=@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@%+#+---=---=====-+#%@@%#+-------------+#+#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@%*=--=++**###***+---===-=+****##**++=--=*%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@%==-*%@@@@@@@@@@@@+-----=*@@@@@@@@@@@@@*===%@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@*-=-%@@@@@@@@@@@@@+==----+@@@@@@@@@@@@@@=-=*@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@+=-#@@@@@@@@@@@@@=------=@@@@@@@@@@@@@#-=+@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@%+=-+@@@@@@@@@@@%*--+%%+=-*%@@@@@@@@@@@+-==%@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@%%@@@#=-==-+#%%%%%%#*==-=+%@@@+=--=*##%%%%%#+-----#@@@@%@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@*-=#@@#=--=---====-==----=%@%%@%=-=----------------#@@%=-+@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@%=+%@@@@#+---==--=-------#@@*+@@#---=------=---==#@@@@@+=#@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@*+*@@@*#@@@@@@@*==-=**+---=---*@*-=*@#-----==+**=-=-+%@@@@@@%+@@@#++%@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@#-=-%@@*#@@@@@@@@@%%@@@@=--------=---=--=----=@@@@%%%@@@@@@@@#+@@%-==*@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@#=%@@@#*********++@@@#+-==--==---===---==----=*@@@*+**********@@@%=#@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@*#%%%%%%%%%%%%=#+@@@=--=++==*+=-+*==+*==+=----%@@****%%%%%%%@@@%#+@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@%*******++*+++#*@@@==-+@@#-#@+-%@==@%-*@@+-==@@@**##=+++****+**%@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@+*=%**@@+--=@@@%%@%%@@%%@@%%@@+--=@@#+@+#=@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@%===####%%+#%#%+===@@@@@@@@@@@@@@@@@@+--=%#%#+%@+###==-*@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@%*+*%%%+#@@#+*%+-==@@@@@@@@@@@@@@@@@@=-==%*+*%@#+#%%#++%@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@**%@@@@+---=++=#@@@@@@@@%=++=---+@@@@%**%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%+***%#=----=-*%@@@@@@%*------=*%***+%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%*===+-=-=#%%#+==----=*%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%#=--=--==--==-=#%%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%%*=----=*#%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%%#%@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
"""
    console.print(ascii_art, style="bold bright_yellow")
    console.print("GoldMAC", style="bold gold1")
    console.print("Author: GoldSkull-777", style="bold cyan")
    console.print("I Live For This Shi*t\n", style="bold magenta")
    # ===== END BANNER =====

    console.print(
        Panel.fit(
            "🎭 [bold cyan]GoldMAC[/bold cyan] — Anonymous MAC Rotator with Vendor OUI\n",
            box=box.DOUBLE
        )
    )

    # ---- ORIGINAL LOGIC CONTINUES UNCHANGED ----
    check_dependency("macchanger")
    check_dependency("ip")
    check_dependency("rich")

    while True:
        interfaces = get_interfaces()
        table = Table(title="📡 Available Interfaces", box=box.MINIMAL_DOUBLE_HEAD, highlight=True)
        table.add_column("ID", justify="center")
        table.add_column("Interface")
        table.add_column("Current MAC")

        if not interfaces:
            console.print("[red]❌ No interfaces found. Plug in a card or enable Wi-Fi...[/red]")
            time.sleep(2)
            continue

        for i, iface in enumerate(interfaces, 1):
            table.add_row(str(i), iface, get_mac(iface))

        console.print(table)
        choice = console.input("[cyan]👉 Select interface by number: [/cyan]")

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(interfaces):
                console.print("[red]❌ Invalid selection[/red]")
                continue
            selected_iface = interfaces[idx]
            break
        except ValueError:
            console.print("[red]❌ Please enter a number[/red]")

    original_mac[selected_iface] = get_mac(selected_iface)
    console.print(f"[green]✅ Selected {selected_iface} (Original MAC: {original_mac[selected_iface]})[/green]")
    log_event(f"🎯 Selected interface {selected_iface} with original MAC {original_mac[selected_iface]}")

    console.print("\n[cyan]🔧 Choose spoofing mode:[/cyan]")
    console.print(" [1] 🎲 Fully random MACs")
    console.print(" [2] 🏷️  Vendor OUI spoofed MACs")

    while True:
        mode_choice = console.input("[cyan]👉 Select option (1 or 2): [/cyan]")
        if mode_choice == "1":
            spoof_mode = "random"
            console.print("[green]✅ Random mode selected[/green]")
            break
        elif mode_choice == "2":
            spoof_mode = "vendor"
            console.print("\n[cyan]🏷️ Available Vendors:[/cyan]")
            for i, vendor in enumerate(VENDOR_OUIS.keys(), 1):
                console.print(f" [{i}] {vendor} ({VENDOR_OUIS[vendor]})")

            selected_vendor = list(VENDOR_OUIS.keys())[int(console.input("Vendor: ")) - 1]
            break

    interval = int(console.input("[cyan]⏱️ Enter MAC rotation interval in minutes: [/cyan]"))

    with Live(console=console, refresh_per_second=1) as live:
        countdown = interval * 60
        while running:
            panel = Panel.fit(
                f"[bold cyan]Interface:[/bold cyan] {selected_iface}\n"
                f"[bold cyan]Current MAC:[/bold cyan] {get_mac(selected_iface)}\n"
                f"[bold cyan]Mode:[/bold cyan] {spoof_mode}{' ('+selected_vendor+')' if selected_vendor else ''}\n"
                f"[bold cyan]Next Change In:[/bold cyan] {countdown}s\n"
                f"[bold cyan]Time:[/bold cyan] {datetime.now().strftime('%H:%M:%S')}\n",
                title="🎭 GoldMAC Monitor",
                border_style="magenta"
            )
            live.update(panel)

            time.sleep(1)
            countdown -= 1

            if countdown <= 0:
                change_mac_random(selected_iface)
                countdown = interval * 60

if __name__ == "__main__":
    main()
