"""Fail-closed USB destination discovery and validation.

Never formats, never repartitions, never writes the Windows system drive.
Never auto-selects when more than one removable destination exists.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from r5_developer_hermes.recovery.contract import (
    USB_AMBIGUOUS,
    USB_INSUFFICIENT_SPACE,
    USB_LAYOUT_ROOT_NAME,
    USB_NOT_CONFIRMED,
    USB_NOT_REMOVABLE,
    USB_RECOMMENDED_LABEL,
    USB_SYSTEM_DRIVE,
)


DriveEnumerator = Callable[[], list["UsbDrive"]]
MappingLike = dict[str, Any]

_DRIVE_LETTER = re.compile(r"^([A-Za-z]):")


@dataclass(frozen=True)
class UsbDrive:
    root: str
    letter: str
    label: str = ""
    bus_type: str = ""
    drive_type: int | None = None
    removable: bool = False
    usb_bus: bool = False
    free_bytes: int = 0
    total_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "letter": self.letter,
            "label": self.label,
            "bus_type": self.bus_type,
            "removable": self.removable,
            "usb_bus": self.usb_bus,
            "free_bytes": self.free_bytes,
            "recommended_label_match": self.label.upper() == USB_RECOMMENDED_LABEL,
        }


@dataclass
class UsbDestination:
    requested: str
    volume_root: str
    recovery_root: str
    drive: UsbDrive | None = None
    confirmed: bool = False
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested": self.requested,
            "volume_root": self.volume_root,
            "recovery_root": self.recovery_root,
            "drive": self.drive.to_dict() if self.drive else None,
            "confirmed": self.confirmed,
            "findings": list(self.findings),
        }


class UsbDestinationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def windows_system_drive() -> str:
    raw = os.environ.get("SystemDrive") or os.environ.get("SYSTEMDRIVE") or "C:"
    letter = raw.rstrip("\\/")
    if not letter.endswith(":"):
        letter = f"{letter}:"
    return letter.upper()


def volume_root_of(path: str | Path) -> str:
    resolved = Path(path).expanduser()
    try:
        resolved = resolved.resolve()
    except OSError:
        resolved = Path(os.path.abspath(str(resolved)))
    match = _DRIVE_LETTER.match(str(resolved))
    if match:
        return f"{match.group(1).upper()}:\\"
    anchor = resolved.anchor
    if anchor:
        return str(Path(anchor))
    raise UsbDestinationError(USB_NOT_REMOVABLE, "destination has no volume root")


def is_system_drive_path(path: str | Path, *, system_drive: str | None = None) -> bool:
    root = volume_root_of(path).rstrip("\\/").upper()
    system = (system_drive or windows_system_drive()).rstrip("\\/").upper()
    return root == system


def recovery_root_for(usb_root: str | Path) -> Path:
    target = Path(usb_root)
    if target.name.upper() == USB_LAYOUT_ROOT_NAME.upper():
        return target
    return target / USB_LAYOUT_ROOT_NAME


def _parse_drive_type(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_logical_disk_records(records: Iterable[MappingLike]) -> list[UsbDrive]:
    drives: list[UsbDrive] = []
    for raw in records:
        device = str(raw.get("DeviceID") or raw.get("root") or "").strip()
        if not device:
            continue
        letter = device.rstrip("\\/").upper()
        if not letter.endswith(":"):
            letter = f"{letter}:"
        drive_type = _parse_drive_type(raw.get("DriveType") if "DriveType" in raw else raw.get("drive_type"))
        bus = str(raw.get("BusType") or raw.get("bus_type") or "").upper()
        removable = drive_type == 2 or bool(raw.get("removable"))
        usb_bus = bus == "USB" or bool(raw.get("usb_bus"))
        drives.append(
            UsbDrive(
                root=f"{letter}\\",
                letter=letter,
                label=str(raw.get("VolumeName") or raw.get("label") or ""),
                bus_type=bus,
                drive_type=drive_type,
                removable=removable,
                usb_bus=usb_bus,
                free_bytes=int(raw.get("FreeSpace") or raw.get("free_bytes") or 0),
                total_bytes=int(raw.get("Size") or raw.get("total_bytes") or 0),
            )
        )
    return drives


def default_windows_drive_enumerator() -> list[UsbDrive]:
    """Best-effort CIM listing. Tests inject a fake enumerator."""
    script = (
        "Get-CimInstance Win32_LogicalDisk | "
        "Select-Object DeviceID,DriveType,VolumeName,FreeSpace,Size | "
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if completed.returncode != 0 or not (completed.stdout or "").strip():
        return []
    import json

    payload = json.loads(completed.stdout)
    if isinstance(payload, dict):
        payload = [payload]
    drives = parse_logical_disk_records(payload)
    return _annotate_usb_bus(drives)


def _annotate_usb_bus(drives: list[UsbDrive]) -> list[UsbDrive]:
    script = (
        "Get-CimInstance Win32_DiskDrive | "
        "Where-Object { $_.InterfaceType -eq 'USB' } | "
        "ForEach-Object { $_.PNPDeviceID } | "
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return drives
    if completed.returncode != 0:
        return drives
    # DriveType=2 is already removable. USB HDDs may appear as type 3; Human
    # must still pass an explicit root. We only mark type-2 as removable here.
    return drives


def list_candidate_usb_drives(
    drives: Iterable[UsbDrive],
    *,
    system_drive: str | None = None,
) -> list[UsbDrive]:
    system = (system_drive or windows_system_drive()).rstrip("\\/").upper()
    candidates: list[UsbDrive] = []
    for drive in drives:
        if drive.letter.rstrip("\\/").upper() == system:
            continue
        if drive.removable or drive.usb_bus:
            candidates.append(drive)
    return candidates


def resolve_destination(
    usb_root: str | Path | None,
    *,
    drives: Iterable[UsbDrive] | None = None,
    enumerator: DriveEnumerator | None = None,
    confirmed: bool = False,
    system_drive: str | None = None,
    required_bytes: int = 0,
) -> UsbDestination:
    discovered = list(drives) if drives is not None else (enumerator or default_windows_drive_enumerator)()
    candidates = list_candidate_usb_drives(discovered, system_drive=system_drive)
    if usb_root is None or str(usb_root).strip() == "":
        if len(candidates) == 0:
            raise UsbDestinationError(USB_NOT_REMOVABLE, "no removable/USB recovery destination found")
        if len(candidates) > 1:
            raise UsbDestinationError(
                USB_AMBIGUOUS,
                "multiple removable drives present; pass -UsbRoot explicitly",
            )
        raise UsbDestinationError(
            USB_NOT_CONFIRMED,
            f"one removable drive {candidates[0].root} found; Human must pass -UsbRoot and confirm",
        )

    requested = str(usb_root).strip()
    if is_system_drive_path(requested, system_drive=system_drive):
        raise UsbDestinationError(USB_SYSTEM_DRIVE, "refusing Windows system drive as recovery destination")
    volume = volume_root_of(requested)
    if is_system_drive_path(volume, system_drive=system_drive):
        raise UsbDestinationError(USB_SYSTEM_DRIVE, "refusing Windows system drive as recovery destination")

    matched = next((item for item in discovered if item.root.rstrip("\\/").upper() == volume.rstrip("\\/").upper()), None)
    if matched is None:
        # Explicit path still must look like a volume we can classify.
        matched = next((item for item in candidates if item.root.rstrip("\\/").upper() == volume.rstrip("\\/").upper()), None)
    if matched is None or not (matched.removable or matched.usb_bus):
        raise UsbDestinationError(
            USB_NOT_REMOVABLE,
            "destination is not a removable/USB recovery volume",
        )
    if not confirmed:
        raise UsbDestinationError(USB_NOT_CONFIRMED, "USB destination was not explicitly confirmed")
    if required_bytes and matched.free_bytes and matched.free_bytes < required_bytes:
        raise UsbDestinationError(
            USB_INSUFFICIENT_SPACE,
            "USB free space is below the backup size estimate",
        )
    dest = UsbDestination(
        requested=requested,
        volume_root=matched.root,
        recovery_root=str(recovery_root_for(requested if Path(requested).name.upper() == USB_LAYOUT_ROOT_NAME.upper() else matched.root)),
        drive=matched,
        confirmed=True,
    )
    if Path(requested).name.upper() == USB_LAYOUT_ROOT_NAME.upper():
        dest.recovery_root = str(Path(requested))
    else:
        dest.recovery_root = str(Path(matched.root) / USB_LAYOUT_ROOT_NAME)
    return dest


def assert_capacity(drive: UsbDrive, required_bytes: int) -> None:
    if required_bytes <= 0:
        return
    if drive.free_bytes < required_bytes:
        raise UsbDestinationError(
            USB_INSUFFICIENT_SPACE,
            "USB free space is below the backup size estimate",
        )
