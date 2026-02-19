"""
Monitor management for multi-monitor support.
"""
import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from typing import List, Tuple, Optional
import logging
import sys


@dataclass
class MonitorInfo:
    """Information about a monitor."""
    handle: int
    name: str
    primary: bool
    x: int
    y: int
    width: int
    height: int
    work_x: int
    work_y: int
    work_width: int
    work_height: int
    dpi: int
    scale_factor: float
    
    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """Get monitor bounds as (x1, y1, x2, y2)."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get monitor center point."""
        return (self.x + self.width // 2, self.y + self.height // 2)


class MonitorManager:
    """Manage monitor information and DPI scaling with dynamic detection."""
    
    # Windows constants
    MONITOR_DEFAULTTONEAREST = 0x00000002
    MDT_EFFECTIVE_DPI = 0
    PROCESS_PER_MONITOR_DPI_AWARE = 2
    DEFAULT_DPI = 96
    
    def __init__(self):
        """Initialize monitor manager."""
        self.logger = logging.getLogger('CaptiOCR.MonitorManager')
        self.monitors: List[MonitorInfo] = []
        self._dpi_context = None
        # Log current DPI awareness status
        self._log_dpi_awareness_status()
        # Don't set DPI awareness here - it should be set at application startup
        self.refresh_monitors()
    
    def _log_dpi_awareness_status(self):
        """Log current DPI awareness status for debugging."""
        if sys.platform != 'win32':
            self.logger.info("Non-Windows platform - DPI awareness not applicable")
            return
        
        try:
            # Try to get current DPI awareness context (Windows 10 1607+)
            try:
                context = ctypes.windll.user32.GetProcessDpiAwarenessContext()
                awareness = ctypes.windll.user32.GetAwarenessFromDpiAwarenessContext(context)
                awareness_names = {
                    0: "DPI_AWARENESS_INVALID",
                    1: "DPI_AWARENESS_UNAWARE", 
                    2: "DPI_AWARENESS_SYSTEM_AWARE",
                    3: "DPI_AWARENESS_PER_MONITOR_AWARE"
                }
                awareness_name = awareness_names.get(awareness, f"Unknown ({awareness})")
                self.logger.info(f"Current DPI awareness: {awareness_name}")
            except Exception as e:
                self.logger.debug(f"Could not get DPI awareness context: {e}")
                
                # Fallback: check older API
                try:
                    awareness = ctypes.c_int()
                    result = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
                    if result == 0:  # S_OK
                        awareness_names = {
                            0: "PROCESS_DPI_UNAWARE",
                            1: "PROCESS_SYSTEM_DPI_AWARE", 
                            2: "PROCESS_PER_MONITOR_DPI_AWARE"
                        }
                        awareness_name = awareness_names.get(awareness.value, f"Unknown ({awareness.value})")
                        self.logger.info(f"Current DPI awareness: {awareness_name}")
                except Exception as e2:
                    self.logger.debug(f"Could not get DPI awareness (fallback): {e2}")
                    
        except Exception as e:
            self.logger.debug(f"Error logging DPI awareness status: {e}")
    
    def refresh_monitors(self) -> bool:
        """
        Refresh monitor information. Called on START button and when needed.
        
        Returns:
            True if monitors were successfully detected
        """
        old_count = len(self.monitors)
        self.monitors.clear()
        
        if sys.platform != 'win32':
            self._add_default_monitor()
            new_count = len(self.monitors)
            self.logger.info(f"Monitor refresh: {old_count} -> {new_count} monitor(s) (non-Windows)")
            return new_count > 0
        
        try:
            # Temporarily set DPI awareness just for monitor detection
            # First enumerate monitors without DPI awareness to get correct positions
            # Define proper Win32 callback signature for EnumDisplayMonitors
            # BOOL CALLBACK MonitorEnumProc(HMONITOR hMonitor, HDC hdcMonitor, LPRECT lprcMonitor, LPARAM dwData)
            MonitorEnumProc = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                ctypes.wintypes.HANDLE,  # HMONITOR (pointer-sized)
                ctypes.wintypes.HDC,     # HDC (pointer-sized)
                ctypes.POINTER(ctypes.wintypes.RECT),  # LPRECT
                ctypes.wintypes.LPARAM   # LPARAM (pointer-sized)
            )
            
            # Callback function
            def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                self._process_monitor(hMonitor)
                return True
            
            # Enumerate monitors
            proc = MonitorEnumProc(callback)
            success = ctypes.windll.user32.EnumDisplayMonitors(0, 0, proc, 0)
            
            if not success or len(self.monitors) == 0:
                self.logger.warning("Monitor enumeration failed, adding default monitor")
                self._add_default_monitor()
            
            # Update DPI for each monitor
            if len(self.monitors) > 0:
                self.logger.info("Starting DPI detection for all monitors...")
                for i, monitor in enumerate(self.monitors):
                    if monitor.handle:
                        self.logger.info(f"Detecting DPI for Monitor {i+1} ({monitor.name}, handle={monitor.handle})")
                        dpi = self._get_monitor_dpi(monitor.handle)
                        monitor.dpi = dpi
                        monitor.scale_factor = dpi / self.DEFAULT_DPI
                        self.logger.info(f"Monitor {i+1} final DPI: {dpi}, Scale: {monitor.scale_factor:.2f}")
                            
                    # Log warning if DPI detection may have failed
                    if monitor.dpi == 96:
                        if i == 0:  # Primary monitor
                            self.logger.warning(f"Primary monitor showing 96 DPI - this may indicate DPI detection issues")
                        else:  # Secondary monitors
                            self.logger.warning(f"Monitor {i+1} DPI detection may have failed (showing 96 DPI)")
                
                self.logger.info("DPI detection completed for all monitors")
            
            new_count = len(self.monitors)
            self.logger.info(f"Monitor refresh: {old_count} -> {new_count} monitor(s)")
            
            # Log monitor details
            for i, monitor in enumerate(self.monitors):
                self.logger.info(
                    f"Monitor {i+1}: {monitor.name} - {monitor.width}x{monitor.height} "
                    f"@ ({monitor.x},{monitor.y}) - DPI={monitor.dpi} Scale={monitor.scale_factor:.2f}"
                )
            
            
            return new_count > 0
            
        except Exception as e:
            self.logger.error(f"Error refreshing monitors: {e}")
            self._add_default_monitor()
            return len(self.monitors) > 0
    
    def _process_monitor(self, hMonitor: int) -> None:
        """Process a single monitor."""
        try:
            # Get monitor info
            class MONITORINFOEX(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.wintypes.DWORD),
                    ("rcMonitor", ctypes.wintypes.RECT),
                    ("rcWork", ctypes.wintypes.RECT),
                    ("dwFlags", ctypes.wintypes.DWORD),
                    ("szDevice", ctypes.c_wchar * 32)
                ]
            
            info = MONITORINFOEX()
            info.cbSize = ctypes.sizeof(MONITORINFOEX)
            
            if not ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                return
            
            # Get DPI for this specific monitor
            dpi = self._get_monitor_dpi(hMonitor)
            
            # Create monitor info
            monitor = MonitorInfo(
                handle=hMonitor,
                name=info.szDevice,
                primary=bool(info.dwFlags & 1),  # MONITORINFOF_PRIMARY
                x=info.rcMonitor.left,
                y=info.rcMonitor.top,
                width=info.rcMonitor.right - info.rcMonitor.left,
                height=info.rcMonitor.bottom - info.rcMonitor.top,
                work_x=info.rcWork.left,
                work_y=info.rcWork.top,
                work_width=info.rcWork.right - info.rcWork.left,
                work_height=info.rcWork.bottom - info.rcWork.top,
                dpi=dpi,
                scale_factor=dpi / self.DEFAULT_DPI
            )
            
            self.monitors.append(monitor)
            
        except Exception as e:
            self.logger.error(f"Error processing monitor: {e}")
    
    def _get_monitor_dpi(self, hMonitor: int) -> int:
        """Get DPI for a specific monitor with multiple fallback methods."""
        self.logger.debug(f"Getting DPI for monitor handle: {hMonitor}")
        
        # Method 1: GetDpiForMonitor (most accurate for per-monitor DPI)
        try:
            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()
            
            result = ctypes.windll.shcore.GetDpiForMonitor(
                hMonitor,
                self.MDT_EFFECTIVE_DPI,
                ctypes.byref(dpi_x),
                ctypes.byref(dpi_y)
            )
            
            if result == 0:  # S_OK
                self.logger.info(f"GetDpiForMonitor success for monitor {hMonitor}: {dpi_x.value} DPI")
                return dpi_x.value
            else:
                self.logger.warning(f"GetDpiForMonitor failed with HRESULT: 0x{result:08X}")
        except Exception as e:
            self.logger.warning(f"GetDpiForMonitor exception: {e}")
        
        # Method 2: GetScaleFactorForMonitor (Windows 8.1+)
        try:
            scale_factor = ctypes.c_uint()
            result = ctypes.windll.shcore.GetScaleFactorForMonitor(hMonitor, ctypes.byref(scale_factor))
            if result == 0:  # S_OK
                # Scale factor is a percentage (100, 125, 150, etc.)
                dpi = int(self.DEFAULT_DPI * (scale_factor.value / 100.0))
                self.logger.info(f"GetScaleFactorForMonitor success for monitor {hMonitor}: {scale_factor.value}% = {dpi} DPI")
                return dpi
            else:
                self.logger.warning(f"GetScaleFactorForMonitor failed with HRESULT: 0x{result:08X}")
        except Exception as e:
            self.logger.warning(f"GetScaleFactorForMonitor exception: {e}")
        
        # Method 3: Get DPI from monitor device context
        try:
            # Get monitor info to get device name
            class MONITORINFOEX(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.wintypes.DWORD),
                    ("rcMonitor", ctypes.wintypes.RECT),
                    ("rcWork", ctypes.wintypes.RECT),
                    ("dwFlags", ctypes.wintypes.DWORD),
                    ("szDevice", ctypes.c_wchar * 32)
                ]
            
            info = MONITORINFOEX()
            info.cbSize = ctypes.sizeof(MONITORINFOEX)
            
            if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                # Create DC for this specific monitor
                hdc = ctypes.windll.user32.CreateDCW(info.szDevice, None, None, None)
                if hdc:
                    dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                    ctypes.windll.gdi32.DeleteDC(hdc)
                    if dpi > 0:
                        self.logger.info(f"Monitor DC DPI for {info.szDevice}: {dpi} DPI")
                        return dpi
        except Exception as e:
            self.logger.warning(f"Monitor DC DPI detection exception: {e}")
        
        # Method 4: System DPI fallback
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)
            self.logger.warning(f"Using system DPI fallback: {dpi} DPI")
            return dpi
        except Exception as e:
            self.logger.error(f"System DPI fallback failed: {e}")
        
        # Final fallback
        self.logger.error(f"All DPI detection methods failed for monitor {hMonitor}, using default {self.DEFAULT_DPI} DPI")
        return self.DEFAULT_DPI
    
    def _add_default_monitor(self) -> None:
        """Add a default monitor when enumeration fails."""
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            
            monitor = MonitorInfo(
                handle=0,
                name="Display",
                primary=True,
                x=0,
                y=0,
                width=root.winfo_screenwidth(),
                height=root.winfo_screenheight(),
                work_x=0,
                work_y=0,
                work_width=root.winfo_screenwidth(),
                work_height=root.winfo_screenheight(),
                dpi=self.DEFAULT_DPI,
                scale_factor=1.0
            )
            
            root.destroy()
            self.monitors.append(monitor)
            
        except Exception as e:
            self.logger.error(f"Error creating default monitor: {e}")
    
    def get_monitor_from_point(self, x: int, y: int) -> Optional[MonitorInfo]:
        """
        Get the monitor containing a specific point.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Monitor info or None
        """
        self.logger.debug(f"Finding monitor for point ({x}, {y})")
        
        for i, monitor in enumerate(self.monitors):
            bounds = (monitor.x, monitor.y, monitor.x + monitor.width, monitor.y + monitor.height)
            self.logger.debug(f"Monitor {i+1} ({monitor.name}): bounds {bounds}")
            
            if (monitor.x <= x < monitor.x + monitor.width and
                monitor.y <= y < monitor.y + monitor.height):
                self.logger.debug(f"Point ({x}, {y}) found on monitor {i+1}: {monitor.name}")
                return monitor
        
        # Return primary monitor if no match
        primary = self.get_primary_monitor()
        self.logger.debug(f"Point ({x}, {y}) not found on any monitor, returning primary: {primary.name if primary else 'None'}")
        return primary
    
    def get_primary_monitor(self) -> Optional[MonitorInfo]:
        """Get the primary monitor."""
        for monitor in self.monitors:
            if monitor.primary:
                return monitor
        
        return self.monitors[0] if self.monitors else None
    
    def get_virtual_screen_bounds(self) -> Tuple[int, int, int, int]:
        """
        Get the bounds of the virtual screen (all monitors combined).
        
        Returns:
            Tuple of (x, y, width, height) for virtual desktop
        """
        if not self.monitors:
            return (0, 0, 1920, 1080)  # Default fallback
        
        min_x = min(m.x for m in self.monitors)
        min_y = min(m.y for m in self.monitors)
        max_x = max(m.x + m.width for m in self.monitors)
        max_y = max(m.y + m.height for m in self.monitors)
        
        return (min_x, min_y, max_x - min_x, max_y - min_y)
    
    
    def validate_capture_area(self, capture_area: Tuple[int, int, int, int]) -> bool:
        """
        Validate that a capture area is still valid (monitor not disconnected).

        Checks whether the center of the capture area falls within the bounds
        of any currently detected monitor. Unlike get_monitor_from_point (which
        falls back to the primary monitor for general use), this method performs
        a strict bounds check with no fallback.

        Args:
            capture_area: Tuple of (x1, y1, x2, y2)

        Returns:
            True if area is still valid
        """
        if not capture_area or not self.monitors:
            return False

        x1, y1, x2, y2 = capture_area
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        # Strict bounds check: point must actually be inside a monitor
        for monitor in self.monitors:
            if (monitor.x <= center_x < monitor.x + monitor.width and
                    monitor.y <= center_y < monitor.y + monitor.height):
                return True

        return False
    
    def get_monitor_count(self) -> int:
        """Get the number of detected monitors."""
        return len(self.monitors)
    
    def has_multi_monitor(self) -> bool:
        """Check if system has multiple monitors."""
        return len(self.monitors) > 1
    
    def get_scale_factor_for_point(self, x: int, y: int) -> float:
        """
        Get the scale factor for a specific point based on which monitor contains it.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Scale factor for the monitor containing the point
        """
        monitor = self.get_monitor_from_point(x, y)
        if monitor:
            self.logger.debug(f"Scale factor for point ({x}, {y}): {monitor.scale_factor} from monitor {monitor.name}")
            return monitor.scale_factor
        
        self.logger.warning(f"No monitor found for point ({x}, {y}), using default scale 1.0")
        return 1.0

    def get_system_dpi_scale(self) -> float:
        """Get the system DPI scale factor without changing process DPI awareness."""
        try:
            # Method 1: Use GetScaleFactorForDevice
            try:
                scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
                if scale_factor > 0:
                    return scale_factor
            except:
                pass
            
            # Method 2: Use tkinter (often more reliable)
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                scale_factor = root.winfo_fpixels('1i') / 96.0
                root.destroy()
                if scale_factor > 0:
                    return scale_factor
            except:
                pass
                
            return 1.0
        except:
            return 1.0
    
