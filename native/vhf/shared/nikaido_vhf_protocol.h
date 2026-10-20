#pragma once

/*
 * Contrato binario compartido por el driver y el cliente de laboratorio.
 * Los consumidores deben incluir primero ntddk.h o Windows.h.
 */

#include <guiddef.h>

#define NIKAIDO_VHF_PROTOCOL_MAGIC 0x3248564EUL /* "NVH2" en little-endian */
#define NIKAIDO_VHF_PROTOCOL_VERSION 1U
#define NIKAIDO_VHF_REPORT_ID 1U
#define NIKAIDO_VHF_INPUT_REPORT_SIZE 16U
#define NIKAIDO_VHF_WATCHDOG_TIMEOUT_MS 500U

DEFINE_GUID(
    GUID_DEVINTERFACE_NIKAIDO_VHF,
    0x8e44f641,
    0x62a9,
    0x4b53,
    0x9a,
    0x9c,
    0xb3,
    0x59,
    0x46,
    0xb8,
    0xf1,
    0xc2
);

#define IOCTL_NIKAIDO_VHF_SUBMIT_INPUT \
    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_WRITE_DATA)
#define IOCTL_NIKAIDO_VHF_NEUTRALIZE \
    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_WRITE_DATA)
#define IOCTL_NIKAIDO_VHF_GET_STATUS \
    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_READ_DATA)

#define NIKAIDO_VHF_STATUS_CLIENT_CONNECTED 0x00000001UL
#define NIKAIDO_VHF_STATUS_REPORT_NEUTRAL 0x00000002UL
#define NIKAIDO_VHF_STATUS_VHF_STARTED 0x00000004UL

#pragma pack(push, 1)

typedef struct _NIKAIDO_HID_INPUT_REPORT {
    UCHAR ReportId;
    USHORT Buttons;
    UCHAR Hat;
    SHORT LeftX;
    SHORT LeftY;
    SHORT RightX;
    SHORT RightY;
    USHORT LeftTrigger;
    USHORT RightTrigger;
} NIKAIDO_HID_INPUT_REPORT, *PNIKAIDO_HID_INPUT_REPORT;

typedef struct _NIKAIDO_VHF_INPUT_MESSAGE {
    ULONG Magic;
    USHORT ProtocolVersion;
    USHORT MessageSize;
    ULONGLONG Sequence;
    NIKAIDO_HID_INPUT_REPORT Report;
} NIKAIDO_VHF_INPUT_MESSAGE, *PNIKAIDO_VHF_INPUT_MESSAGE;

typedef struct _NIKAIDO_VHF_STATUS {
    ULONG Magic;
    USHORT ProtocolVersion;
    USHORT StatusSize;
    ULONG Flags;
    ULONG WatchdogTrips;
    ULONGLONG LastSequence;
    NIKAIDO_HID_INPUT_REPORT CurrentReport;
} NIKAIDO_VHF_STATUS, *PNIKAIDO_VHF_STATUS;

#pragma pack(pop)
