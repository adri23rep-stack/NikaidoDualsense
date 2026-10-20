#include <ntddk.h>
#include <wdf.h>
#include <vhf.h>
#include <initguid.h>

#include "../shared/nikaido_vhf_protocol.h"

C_ASSERT(sizeof(NIKAIDO_HID_INPUT_REPORT) == NIKAIDO_VHF_INPUT_REPORT_SIZE);
C_ASSERT(sizeof(NIKAIDO_VHF_INPUT_MESSAGE) == 32);
C_ASSERT(sizeof(NIKAIDO_VHF_STATUS) == 40);

static const UCHAR g_NikaidoGamepadReportDescriptor[] = {
    0x05, 0x01,                         /* Usage Page (Generic Desktop) */
    0x09, 0x05,                         /* Usage (Game Pad) */
    0xA1, 0x01,                         /* Collection (Application) */
    0x85, NIKAIDO_VHF_REPORT_ID,        /* Report ID */
    0x05, 0x09,                         /* Usage Page (Button) */
    0x19, 0x01,                         /* Usage Minimum (1) */
    0x29, 0x0E,                         /* Usage Maximum (14) */
    0x15, 0x00,                         /* Logical Minimum (0) */
    0x25, 0x01,                         /* Logical Maximum (1) */
    0x75, 0x01,                         /* Report Size (1) */
    0x95, 0x0E,                         /* Report Count (14) */
    0x81, 0x02,                         /* Input (Data, Variable, Absolute) */
    0x75, 0x01,                         /* Two padding bits */
    0x95, 0x02,
    0x81, 0x03,                         /* Input (Constant) */
    0x05, 0x01,                         /* Usage Page (Generic Desktop) */
    0x09, 0x39,                         /* Usage (Hat switch) */
    0x15, 0x00,
    0x25, 0x07,
    0x35, 0x00,
    0x46, 0x3B, 0x01,
    0x65, 0x14,
    0x75, 0x04,
    0x95, 0x01,
    0x81, 0x42,                         /* Input with null state */
    0x65, 0x00,
    0x75, 0x04,
    0x95, 0x01,
    0x81, 0x03,                         /* Four padding bits */
    0x09, 0x30,                         /* X */
    0x09, 0x31,                         /* Y */
    0x09, 0x33,                         /* Rx */
    0x09, 0x34,                         /* Ry */
    0x16, 0x00, 0x80,                   /* Logical Minimum (-32768) */
    0x26, 0xFF, 0x7F,                   /* Logical Maximum (32767) */
    0x75, 0x10,
    0x95, 0x04,
    0x81, 0x02,
    0x09, 0x32,                         /* Z: L2 */
    0x09, 0x35,                         /* Rz: R2 */
    0x15, 0x00,
    0x27, 0xFF, 0xFF, 0x00, 0x00,       /* Logical Maximum (65535) */
    0x75, 0x10,
    0x95, 0x02,
    0x81, 0x02,
    0xC0                                /* End Collection */
};

static const NIKAIDO_HID_INPUT_REPORT g_NeutralReport = {
    NIKAIDO_VHF_REPORT_ID,
    0,
    8,
    0,
    0,
    0,
    0,
    0,
    0
};

typedef struct _DEVICE_CONTEXT {
    VHFHANDLE VhfHandle;
    WDFTIMER WatchdogTimer;
    NIKAIDO_HID_INPUT_REPORT CurrentReport;
    ULONGLONG LastSequence;
    ULONG WatchdogTrips;
    BOOLEAN ClientConnected;
    BOOLEAN IsNeutral;
    BOOLEAN VhfStarted;
    BOOLEAN Stopping;
} DEVICE_CONTEXT, *PDEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DEVICE_CONTEXT, DeviceGetContext);

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD NikaidoEvtDeviceAdd;
EVT_WDF_OBJECT_CONTEXT_CLEANUP NikaidoEvtDeviceCleanup;
EVT_WDF_DEVICE_FILE_CREATE NikaidoEvtDeviceFileCreate;
EVT_WDF_FILE_CLEANUP NikaidoEvtFileCleanup;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL NikaidoEvtIoDeviceControl;
EVT_WDF_TIMER NikaidoEvtWatchdog;
EVT_WDF_DEVICE_D0_ENTRY NikaidoEvtDeviceD0Entry;
EVT_WDF_DEVICE_D0_EXIT NikaidoEvtDeviceD0Exit;

static BOOLEAN
NikaidoReportIsValid(
    _In_ const NIKAIDO_HID_INPUT_REPORT* Report
)
{
    if (Report->ReportId != NIKAIDO_VHF_REPORT_ID) {
        return FALSE;
    }
    if ((Report->Buttons & 0xC000U) != 0U) {
        return FALSE;
    }
    if (Report->Hat > 8U) {
        return FALSE;
    }
    return TRUE;
}

static BOOLEAN
NikaidoReportIsNeutral(
    _In_ const NIKAIDO_HID_INPUT_REPORT* Report
)
{
    return RtlCompareMemory(
        Report,
        &g_NeutralReport,
        sizeof(g_NeutralReport)
    ) == sizeof(g_NeutralReport);
}

static NTSTATUS
NikaidoSubmitReport(
    _Inout_ PDEVICE_CONTEXT Context,
    _In_ const NIKAIDO_HID_INPUT_REPORT* Report
)
{
    HID_XFER_PACKET packet;
    NIKAIDO_HID_INPUT_REPORT localReport;
    NTSTATUS status;

    if (Context->Stopping || !Context->VhfStarted || Context->VhfHandle == NULL) {
        return STATUS_DEVICE_NOT_READY;
    }
    if (!NikaidoReportIsValid(Report)) {
        return STATUS_INVALID_PARAMETER;
    }

    localReport = *Report;
    RtlZeroMemory(&packet, sizeof(packet));
    packet.reportBuffer = (PUCHAR)&localReport;
    packet.reportBufferLen = (ULONG)sizeof(localReport);
    packet.reportId = localReport.ReportId;

    status = VhfReadReportSubmit(Context->VhfHandle, &packet);
    if (NT_SUCCESS(status)) {
        Context->CurrentReport = localReport;
        Context->IsNeutral = NikaidoReportIsNeutral(&localReport);
    }
    return status;
}

static NTSTATUS
NikaidoSubmitNeutral(
    _Inout_ PDEVICE_CONTEXT Context
)
{
    return NikaidoSubmitReport(Context, &g_NeutralReport);
}

static NTSTATUS
NikaidoValidateMessage(
    _In_ const NIKAIDO_VHF_INPUT_MESSAGE* Message,
    _In_ size_t BufferLength,
    _In_ ULONGLONG LastSequence
)
{
    if (BufferLength != sizeof(*Message)) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    if (Message->Magic != NIKAIDO_VHF_PROTOCOL_MAGIC ||
        Message->ProtocolVersion != NIKAIDO_VHF_PROTOCOL_VERSION ||
        Message->MessageSize != (USHORT)sizeof(*Message)) {
        return STATUS_REVISION_MISMATCH;
    }
    if (Message->Sequence == 0 || Message->Sequence <= LastSequence) {
        return STATUS_INVALID_PARAMETER;
    }
    if (!NikaidoReportIsValid(&Message->Report)) {
        return STATUS_INVALID_PARAMETER;
    }
    return STATUS_SUCCESS;
}

NTSTATUS
DriverEntry(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath
)
{
    WDF_DRIVER_CONFIG config;

    WDF_DRIVER_CONFIG_INIT(&config, NikaidoEvtDeviceAdd);
    return WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE
    );
}

NTSTATUS
NikaidoEvtDeviceAdd(
    _In_ WDFDRIVER Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit
)
{
    WDF_OBJECT_ATTRIBUTES deviceAttributes;
    WDF_PNPPOWER_EVENT_CALLBACKS powerCallbacks;
    WDF_FILEOBJECT_CONFIG fileConfig;
    WDF_IO_QUEUE_CONFIG queueConfig;
    WDF_TIMER_CONFIG timerConfig;
    WDF_OBJECT_ATTRIBUTES timerAttributes;
    VHF_CONFIG vhfConfig;
    WDFDEVICE device;
    PDEVICE_CONTEXT context;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(Driver);

    WdfDeviceInitSetDeviceType(DeviceInit, FILE_DEVICE_UNKNOWN);
    WdfDeviceInitSetExclusive(DeviceInit, TRUE);

    WDF_PNPPOWER_EVENT_CALLBACKS_INIT(&powerCallbacks);
    powerCallbacks.EvtDeviceD0Entry = NikaidoEvtDeviceD0Entry;
    powerCallbacks.EvtDeviceD0Exit = NikaidoEvtDeviceD0Exit;
    WdfDeviceInitSetPnpPowerEventCallbacks(DeviceInit, &powerCallbacks);

    WDF_FILEOBJECT_CONFIG_INIT(
        &fileConfig,
        NikaidoEvtDeviceFileCreate,
        WDF_NO_EVENT_CALLBACK,
        NikaidoEvtFileCleanup
    );
    WdfDeviceInitSetFileObjectConfig(
        DeviceInit,
        &fileConfig,
        WDF_NO_OBJECT_ATTRIBUTES
    );

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&deviceAttributes, DEVICE_CONTEXT);
    deviceAttributes.EvtCleanupCallback = NikaidoEvtDeviceCleanup;
    deviceAttributes.ExecutionLevel = WdfExecutionLevelPassive;
    deviceAttributes.SynchronizationScope = WdfSynchronizationScopeDevice;

    status = WdfDeviceCreate(&DeviceInit, &deviceAttributes, &device);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    context = DeviceGetContext(device);
    RtlZeroMemory(context, sizeof(*context));
    context->CurrentReport = g_NeutralReport;
    context->IsNeutral = TRUE;

    status = WdfDeviceCreateDeviceInterface(
        device,
        &GUID_DEVINTERFACE_NIKAIDO_VHF,
        NULL
    );
    if (!NT_SUCCESS(status)) {
        return status;
    }

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(
        &queueConfig,
        WdfIoQueueDispatchSequential
    );
    queueConfig.EvtIoDeviceControl = NikaidoEvtIoDeviceControl;
    status = WdfIoQueueCreate(
        device,
        &queueConfig,
        WDF_NO_OBJECT_ATTRIBUTES,
        WDF_NO_HANDLE
    );
    if (!NT_SUCCESS(status)) {
        return status;
    }

    WDF_TIMER_CONFIG_INIT(&timerConfig, NikaidoEvtWatchdog);
    WDF_OBJECT_ATTRIBUTES_INIT(&timerAttributes);
    timerAttributes.ParentObject = device;
    timerAttributes.ExecutionLevel = WdfExecutionLevelPassive;
    status = WdfTimerCreate(
        &timerConfig,
        &timerAttributes,
        &context->WatchdogTimer
    );
    if (!NT_SUCCESS(status)) {
        return status;
    }

    VHF_CONFIG_INIT(
        &vhfConfig,
        WdfDeviceWdmGetDeviceObject(device),
        (USHORT)sizeof(g_NikaidoGamepadReportDescriptor),
        (PUCHAR)g_NikaidoGamepadReportDescriptor
    );
    /* VID/PID cero: identidad experimental genérica, sin suplantar terceros. */
    vhfConfig.VendorID = 0;
    vhfConfig.ProductID = 0;
    vhfConfig.VersionNumber = 0x0002;

    status = VhfCreate(&vhfConfig, &context->VhfHandle);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    status = VhfStart(context->VhfHandle);
    if (!NT_SUCCESS(status)) {
        VhfDelete(context->VhfHandle, TRUE);
        context->VhfHandle = NULL;
        return status;
    }
    context->VhfStarted = TRUE;

    status = NikaidoSubmitNeutral(context);
    if (!NT_SUCCESS(status)) {
        context->VhfStarted = FALSE;
        VhfDelete(context->VhfHandle, TRUE);
        context->VhfHandle = NULL;
        return status;
    }

    return STATUS_SUCCESS;
}

VOID
NikaidoEvtDeviceCleanup(
    _In_ WDFOBJECT DeviceObject
)
{
    PDEVICE_CONTEXT context = DeviceGetContext((WDFDEVICE)DeviceObject);

    context->Stopping = TRUE;
    if (context->WatchdogTimer != NULL) {
        WdfTimerStop(context->WatchdogTimer, TRUE);
    }
    if (context->VhfHandle != NULL) {
        if (context->VhfStarted) {
            context->Stopping = FALSE;
            (VOID)NikaidoSubmitNeutral(context);
            context->Stopping = TRUE;
            context->VhfStarted = FALSE;
        }
        VhfDelete(context->VhfHandle, TRUE);
        context->VhfHandle = NULL;
    }
}

VOID
NikaidoEvtDeviceFileCreate(
    _In_ WDFDEVICE Device,
    _In_ WDFREQUEST Request,
    _In_ WDFFILEOBJECT FileObject
)
{
    PDEVICE_CONTEXT context = DeviceGetContext(Device);
    NTSTATUS status;

    UNREFERENCED_PARAMETER(FileObject);

    if (context->Stopping || !context->VhfStarted) {
        WdfRequestComplete(Request, STATUS_DEVICE_NOT_READY);
        return;
    }

    context->ClientConnected = TRUE;
    context->LastSequence = 0;
    WdfTimerStop(context->WatchdogTimer, FALSE);
    status = NikaidoSubmitNeutral(context);
    if (!NT_SUCCESS(status)) {
        context->ClientConnected = FALSE;
    }
    WdfRequestComplete(Request, status);
}

VOID
NikaidoEvtFileCleanup(
    _In_ WDFFILEOBJECT FileObject
)
{
    WDFDEVICE device = WdfFileObjectGetDevice(FileObject);
    PDEVICE_CONTEXT context = DeviceGetContext(device);

    context->ClientConnected = FALSE;
    WdfTimerStop(context->WatchdogTimer, FALSE);
    if (!context->Stopping && context->VhfStarted) {
        (VOID)NikaidoSubmitNeutral(context);
    }
}

VOID
NikaidoEvtIoDeviceControl(
    _In_ WDFQUEUE Queue,
    _In_ WDFREQUEST Request,
    _In_ size_t OutputBufferLength,
    _In_ size_t InputBufferLength,
    _In_ ULONG IoControlCode
)
{
    WDFDEVICE device = WdfIoQueueGetDevice(Queue);
    PDEVICE_CONTEXT context = DeviceGetContext(device);
    NTSTATUS status = STATUS_INVALID_DEVICE_REQUEST;
    size_t information = 0;

    UNREFERENCED_PARAMETER(OutputBufferLength);
    UNREFERENCED_PARAMETER(InputBufferLength);

    if (IoControlCode == IOCTL_NIKAIDO_VHF_SUBMIT_INPUT) {
        PNIKAIDO_VHF_INPUT_MESSAGE message = NULL;
        size_t bufferLength = 0;

        if (!context->ClientConnected) {
            status = STATUS_DEVICE_NOT_CONNECTED;
        } else {
            status = WdfRequestRetrieveInputBuffer(
                Request,
                sizeof(NIKAIDO_VHF_INPUT_MESSAGE),
                (PVOID*)&message,
                &bufferLength
            );
            if (NT_SUCCESS(status)) {
                status = NikaidoValidateMessage(
                    message,
                    bufferLength,
                    context->LastSequence
                );
            }
            if (NT_SUCCESS(status)) {
                status = NikaidoSubmitReport(context, &message->Report);
            }
            if (NT_SUCCESS(status)) {
                context->LastSequence = message->Sequence;
                if (context->IsNeutral) {
                    WdfTimerStop(context->WatchdogTimer, FALSE);
                } else {
                    WdfTimerStart(
                        context->WatchdogTimer,
                        WDF_REL_TIMEOUT_IN_MS(NIKAIDO_VHF_WATCHDOG_TIMEOUT_MS)
                    );
                }
            }
        }
    } else if (IoControlCode == IOCTL_NIKAIDO_VHF_NEUTRALIZE) {
        WdfTimerStop(context->WatchdogTimer, FALSE);
        status = NikaidoSubmitNeutral(context);
    } else if (IoControlCode == IOCTL_NIKAIDO_VHF_GET_STATUS) {
        PNIKAIDO_VHF_STATUS output = NULL;

        status = WdfRequestRetrieveOutputBuffer(
            Request,
            sizeof(NIKAIDO_VHF_STATUS),
            (PVOID*)&output,
            NULL
        );
        if (NT_SUCCESS(status)) {
            RtlZeroMemory(output, sizeof(*output));
            output->Magic = NIKAIDO_VHF_PROTOCOL_MAGIC;
            output->ProtocolVersion = NIKAIDO_VHF_PROTOCOL_VERSION;
            output->StatusSize = (USHORT)sizeof(*output);
            output->WatchdogTrips = context->WatchdogTrips;
            output->LastSequence = context->LastSequence;
            output->CurrentReport = context->CurrentReport;
            if (context->ClientConnected) {
                output->Flags |= NIKAIDO_VHF_STATUS_CLIENT_CONNECTED;
            }
            if (context->IsNeutral) {
                output->Flags |= NIKAIDO_VHF_STATUS_REPORT_NEUTRAL;
            }
            if (context->VhfStarted) {
                output->Flags |= NIKAIDO_VHF_STATUS_VHF_STARTED;
            }
            information = sizeof(*output);
        }
    }

    WdfRequestCompleteWithInformation(Request, status, information);
}

VOID
NikaidoEvtWatchdog(
    _In_ WDFTIMER Timer
)
{
    WDFDEVICE device = (WDFDEVICE)WdfTimerGetParentObject(Timer);
    PDEVICE_CONTEXT context = DeviceGetContext(device);
    if (context->Stopping || !context->ClientConnected || context->IsNeutral) {
        return;
    }
    if (NT_SUCCESS(NikaidoSubmitNeutral(context))) {
        context->WatchdogTrips += 1;
    }
}

NTSTATUS
NikaidoEvtDeviceD0Entry(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE PreviousState
)
{
    PDEVICE_CONTEXT context = DeviceGetContext(Device);

    UNREFERENCED_PARAMETER(PreviousState);
    if (context->VhfStarted && !context->Stopping) {
        WdfTimerStop(context->WatchdogTimer, FALSE);
        return NikaidoSubmitNeutral(context);
    }
    return STATUS_SUCCESS;
}

NTSTATUS
NikaidoEvtDeviceD0Exit(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE TargetState
)
{
    PDEVICE_CONTEXT context = DeviceGetContext(Device);

    UNREFERENCED_PARAMETER(TargetState);
    if (context->VhfStarted && !context->Stopping) {
        WdfTimerStop(context->WatchdogTimer, FALSE);
        return NikaidoSubmitNeutral(context);
    }
    return STATUS_SUCCESS;
}
