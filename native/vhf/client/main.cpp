#include <Windows.h>
#include <SetupAPI.h>
#include <initguid.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <vector>

#include "../shared/nikaido_vhf_protocol.h"

#pragma comment(lib, "setupapi.lib")

namespace {

constexpr USHORT ButtonCross = 1U << 0;
constexpr USHORT ButtonCircle = 1U << 1;
constexpr USHORT ButtonOptions = 1U << 10;
constexpr USHORT ButtonCreate = 1U << 11;
constexpr USHORT ButtonPs = 1U << 12;
constexpr USHORT ButtonTouchpad = 1U << 13;

struct OpenLabInterfaceResult {
    HANDLE handle;
    DWORD error;
};

DWORD NonzeroError(DWORD error, DWORD fallback) {
    return error == ERROR_SUCCESS ? fallback : error;
}

bool PrintWide(FILE* stream, const wchar_t* format, ...) {
    va_list arguments;
    va_start(arguments, format);
    va_list sizingArguments;
    va_copy(sizingArguments, arguments);
    const int requiredCharacters = _vscwprintf(format, sizingArguments);
    va_end(sizingArguments);

    if (requiredCharacters < 0) {
        va_end(arguments);
        return false;
    }

    std::vector<wchar_t> text(static_cast<size_t>(requiredCharacters) + 1U, L'\0');
    const int formattedCharacters = _vsnwprintf_s(
        text.data(),
        text.size(),
        _TRUNCATE,
        format,
        arguments
    );
    va_end(arguments);
    if (formattedCharacters < 0) {
        return false;
    }

    const DWORD standardHandle = stream == stderr ? STD_ERROR_HANDLE : STD_OUTPUT_HANDLE;
    const HANDLE output = GetStdHandle(standardHandle);
    DWORD consoleMode = 0;
    if (output != nullptr &&
        output != INVALID_HANDLE_VALUE &&
        GetConsoleMode(output, &consoleMode)) {
        DWORD written = 0;
        return WriteConsoleW(
                   output,
                   text.data(),
                   static_cast<DWORD>(formattedCharacters),
                   &written,
                   nullptr
               ) != FALSE &&
            written == static_cast<DWORD>(formattedCharacters);
    }

    const int requiredBytes = WideCharToMultiByte(
        CP_UTF8,
        WC_ERR_INVALID_CHARS,
        text.data(),
        formattedCharacters,
        nullptr,
        0,
        nullptr,
        nullptr
    );
    if (requiredBytes <= 0) {
        return false;
    }

    std::vector<char> utf8(static_cast<size_t>(requiredBytes), '\0');
    const int convertedBytes = WideCharToMultiByte(
        CP_UTF8,
        WC_ERR_INVALID_CHARS,
        text.data(),
        formattedCharacters,
        utf8.data(),
        requiredBytes,
        nullptr,
        nullptr
    );
    if (convertedBytes != requiredBytes) {
        return false;
    }

    const size_t written = std::fwrite(utf8.data(), 1U, utf8.size(), stream);
    std::fflush(stream);
    return written == utf8.size();
}

OpenLabInterfaceResult OpenLabInterface() {
    HDEVINFO deviceInfo = SetupDiGetClassDevsW(
        &GUID_DEVINTERFACE_NIKAIDO_VHF,
        nullptr,
        nullptr,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    );
    if (deviceInfo == INVALID_HANDLE_VALUE) {
        return {
            INVALID_HANDLE_VALUE,
            NonzeroError(GetLastError(), ERROR_GEN_FAILURE),
        };
    }

    SP_DEVICE_INTERFACE_DATA interfaceData{};
    interfaceData.cbSize = sizeof(interfaceData);
    if (!SetupDiEnumDeviceInterfaces(
            deviceInfo,
            nullptr,
            &GUID_DEVINTERFACE_NIKAIDO_VHF,
            0,
            &interfaceData)) {
        const DWORD error = NonzeroError(GetLastError(), ERROR_NO_MORE_ITEMS);
        SetupDiDestroyDeviceInfoList(deviceInfo);
        return {INVALID_HANDLE_VALUE, error};
    }

    DWORD requiredSize = 0;
    const BOOL detailProbeSucceeded = SetupDiGetDeviceInterfaceDetailW(
        deviceInfo,
        &interfaceData,
        nullptr,
        0,
        &requiredSize,
        nullptr
    );
    const DWORD detailProbeError = GetLastError();
    if (!detailProbeSucceeded && detailProbeError != ERROR_INSUFFICIENT_BUFFER) {
        const DWORD error = NonzeroError(detailProbeError, ERROR_INVALID_DATA);
        SetupDiDestroyDeviceInfoList(deviceInfo);
        return {INVALID_HANDLE_VALUE, error};
    }
    if (requiredSize < static_cast<DWORD>(sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W))) {
        SetupDiDestroyDeviceInfoList(deviceInfo);
        return {INVALID_HANDLE_VALUE, ERROR_INVALID_DATA};
    }

    std::vector<BYTE> buffer(requiredSize, 0);
    auto* detail = reinterpret_cast<SP_DEVICE_INTERFACE_DETAIL_DATA_W*>(buffer.data());
    detail->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W);
    if (!SetupDiGetDeviceInterfaceDetailW(
            deviceInfo,
            &interfaceData,
            detail,
            requiredSize,
            nullptr,
            nullptr)) {
        const DWORD error = NonzeroError(GetLastError(), ERROR_INVALID_DATA);
        SetupDiDestroyDeviceInfoList(deviceInfo);
        return {INVALID_HANDLE_VALUE, error};
    }

    HANDLE handle = CreateFileW(
        detail->DevicePath,
        GENERIC_READ | GENERIC_WRITE,
        0,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr
    );
    const DWORD openError = handle == INVALID_HANDLE_VALUE
        ? NonzeroError(GetLastError(), ERROR_OPEN_FAILED)
        : ERROR_SUCCESS;
    SetupDiDestroyDeviceInfoList(deviceInfo);
    return {handle, openError};
}

bool SendInput(
    HANDLE handle,
    ULONGLONG sequence,
    const NIKAIDO_HID_INPUT_REPORT& report
) {
    NIKAIDO_VHF_INPUT_MESSAGE message{};
    DWORD returned = 0;

    message.Magic = NIKAIDO_VHF_PROTOCOL_MAGIC;
    message.ProtocolVersion = NIKAIDO_VHF_PROTOCOL_VERSION;
    message.MessageSize = static_cast<USHORT>(sizeof(message));
    message.Sequence = sequence;
    message.Report = report;

    return DeviceIoControl(
        handle,
        IOCTL_NIKAIDO_VHF_SUBMIT_INPUT,
        &message,
        static_cast<DWORD>(sizeof(message)),
        nullptr,
        0,
        &returned,
        nullptr
    ) != FALSE;
}

bool SendNeutral(HANDLE handle) {
    DWORD returned = 0;
    return DeviceIoControl(
        handle,
        IOCTL_NIKAIDO_VHF_NEUTRALIZE,
        nullptr,
        0,
        nullptr,
        0,
        &returned,
        nullptr
    ) != FALSE;
}

bool ReadStatus(HANDLE handle, NIKAIDO_VHF_STATUS* status) {
    DWORD returned = 0;
    std::memset(status, 0, sizeof(*status));
    if (!DeviceIoControl(
            handle,
            IOCTL_NIKAIDO_VHF_GET_STATUS,
            nullptr,
            0,
            status,
            static_cast<DWORD>(sizeof(*status)),
            &returned,
            nullptr)) {
        return false;
    }
    const bool valid = returned == static_cast<DWORD>(sizeof(*status)) &&
        status->Magic == NIKAIDO_VHF_PROTOCOL_MAGIC &&
        status->ProtocolVersion == NIKAIDO_VHF_PROTOCOL_VERSION &&
        status->StatusSize == static_cast<USHORT>(sizeof(*status));
    if (!valid) {
        SetLastError(ERROR_INVALID_DATA);
    }
    return valid;
}

NIKAIDO_HID_INPUT_REPORT NeutralReport() {
    NIKAIDO_HID_INPUT_REPORT report{};
    report.ReportId = NIKAIDO_VHF_REPORT_ID;
    report.Hat = 8;
    return report;
}

void PrintStatus(const NIKAIDO_VHF_STATUS& status) {
    PrintWide(stdout, L"Nikaido DualSense 3.0.0 Alpha 2.3.0 - estado VHF\n");
    PrintWide(
        stdout,
        L"VHF iniciado: %ls\n",
        (status.Flags & NIKAIDO_VHF_STATUS_VHF_STARTED) ? L"sí" : L"no"
    );
    PrintWide(
        stdout,
        L"Reporte neutral: %ls\n",
        (status.Flags & NIKAIDO_VHF_STATUS_REPORT_NEUTRAL) ? L"sí" : L"no"
    );
    PrintWide(
        stdout,
        L"Última secuencia: %llu\n",
        static_cast<unsigned long long>(status.LastSequence)
    );
    PrintWide(stdout, L"Neutralizaciones por watchdog: %lu\n", status.WatchdogTrips);
}

int RunDemo(HANDLE handle) {
    ULONGLONG sequence = 1;
    NIKAIDO_HID_INPUT_REPORT report = NeutralReport();

    report.Buttons = ButtonCross | ButtonOptions;
    report.Hat = 0;
    report.LeftX = -32768;
    report.LeftY = 32767;
    report.RightX = 32767;
    report.RightY = -32768;
    report.LeftTrigger = 65535;
    report.RightTrigger = 32768;
    if (!SendInput(handle, sequence++, report)) {
        return 4;
    }
    Sleep(100);

    report = NeutralReport();
    report.Buttons = ButtonCircle | ButtonCreate | ButtonPs | ButtonTouchpad;
    report.Hat = 4;
    report.LeftTrigger = 16384;
    report.RightTrigger = 65535;
    if (!SendInput(handle, sequence++, report)) {
        return 4;
    }
    Sleep(100);

    report = NeutralReport();
    if (!SendInput(handle, sequence++, report) || !SendNeutral(handle)) {
        return 4;
    }
    PrintWide(stdout, L"Demostración enviada y cierre neutral solicitado.\n");
    return 0;
}

void PrintUsage() {
    PrintWide(
        stdout,
        L"Uso: NikaidoVhfClient.exe status | neutral | demo\n"
        L"El cliente no instala drivers ni modifica protecciones de Windows.\n"
    );
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    if (argc != 2) {
        PrintUsage();
        return 2;
    }

    const OpenLabInterfaceResult openResult = OpenLabInterface();
    if (openResult.handle == INVALID_HANDLE_VALUE) {
        PrintWide(
            stderr,
            L"No se pudo abrir la interfaz Alpha 2.3.0 (error Win32 %lu). "
            L"Debe existir un paquete compilado y firmado; la interfaz está restringida.\n",
            openResult.error
        );
        return 3;
    }
    const HANDLE handle = openResult.handle;

    int result = 0;
    if (_wcsicmp(argv[1], L"status") == 0) {
        NIKAIDO_VHF_STATUS status{};
        if (!ReadStatus(handle, &status)) {
            result = 4;
        } else {
            PrintStatus(status);
        }
    } else if (_wcsicmp(argv[1], L"neutral") == 0) {
        if (!SendNeutral(handle)) {
            result = 4;
        } else {
            PrintWide(stdout, L"Reporte neutral solicitado.\n");
        }
    } else if (_wcsicmp(argv[1], L"demo") == 0) {
        result = RunDemo(handle);
    } else {
        PrintUsage();
        result = 2;
    }

    if (result == 4) {
        const DWORD error = NonzeroError(GetLastError(), ERROR_GEN_FAILURE);
        PrintWide(stderr, L"La operación falló (error Win32 %lu).\n", error);
    }
    CloseHandle(handle);
    return result;
}
