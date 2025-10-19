#!/usr/bin/env python3
"""
CLI entry point for qPCR Calculator.
Launches the GUI or builds the app with PyInstaller.
"""
import sys
import argparse
from pathlib import Path

def main():
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    DIST_DIR = PROJECT_ROOT / "dist"
    BUILD_DIR = PROJECT_ROOT / "build"
    ENTRY_SCRIPT = PROJECT_ROOT / "gui" / "main_window.py"

    parser = argparse.ArgumentParser(
        description="qPCR Calculator CLI (launch GUI or build executable)"
    )
    parser.add_argument("--build", action="store_true", help="Build app using PyInstaller.")
    parser.add_argument("--onefile", action="store_true", help="Build as single-file executable.")
    parser.add_argument("--slim", action="store_true", help="Slim build: only ship essential Qt plugins and minimal deps.")
    args = parser.parse_args()

    if args.build:
        print("[INFO] Building qPCR Calculator with PyInstaller...")
        try:
            import PyInstaller.__main__ as pyim
        except ImportError:
            print("[ERROR] PyInstaller is not installed. Run: pip install pyinstaller", file=sys.stderr)
            sys.exit(1)
        if not ENTRY_SCRIPT.exists():
            print(f"[ERROR] Entry script not found: {ENTRY_SCRIPT}", file=sys.stderr)
            sys.exit(1)

        # Resolve Qt plugin dir (for selective shipping in --slim mode)
        qt_plugins_dir = None
        try:
            from PySide6 import QtCore  # type: ignore
            qt_plugins_dir = Path(QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.PluginsPath))
        except Exception:
            pass

        # Define pathsep for --add-binary
        pathsep = ";" if sys.platform.startswith("win") else ":"

        # --- Icon conversion helpers ---------------------------------------
        def _png_to_icns(png: Path, out_icns: Path) -> Path | None:
            """Convert a PNG into ICNS using macOS tools (sips + iconutil)."""
            try:
                import subprocess, shutil
                iconset = BUILD_DIR / "_icon.iconset"
                if iconset.exists():
                    shutil.rmtree(iconset)
                iconset.mkdir(parents=True, exist_ok=True)
                sizes = [16, 32, 128, 256, 512]
                for s in sizes:
                    # 1x
                    dest1 = iconset / f"icon_{s}x{s}.png"
                    subprocess.run(["sips", "-z", str(s), str(s), str(png), "--out", str(dest1)],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    # 2x
                    dest2 = iconset / f"icon_{s}x{s}@2x.png"
                    subprocess.run(["sips", "-z", str(s*2), str(s*2), str(png), "--out", str(dest2)],
                                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out_icns)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return out_icns if out_icns.exists() else None
            except Exception as e:
                print(f"[WARN] PNG→ICNS conversion failed: {e}")
                return None

        def _png_to_ico(png: Path, out_ico: Path) -> Path | None:
            """Convert a PNG into ICO using Pillow if available."""
            try:
                from PIL import Image  # type: ignore
                img = Image.open(png).convert("RGBA")
                sizes = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
                img.save(out_ico, format="ICO", sizes=sizes)
                return out_ico if out_ico.exists() else None
            except Exception as e:
                print(f"[WARN] PNG→ICO conversion failed: {e}. Install pillow to enable conversion: pip install pillow")
                return None
            
        if args.slim:
            # SLIM build: avoid broad --collect-all; add only essentials.
            py_args = [
                "--noconfirm", "--clean", "--windowed",
                "--name", "qPCR-Calculator",
                "--distpath", str(DIST_DIR),
                "--workpath", str(BUILD_DIR),
                "--specpath", str(BUILD_DIR),
                # Hidden imports you actually use
                "--hidden-import", "PySide6.QtCore",
                "--hidden-import", "PySide6.QtGui",
                "--hidden-import", "PySide6.QtWidgets",
                # Pandas engines (min): openpyxl, xlsxwriter
                "--hidden-import", "openpyxl",
                "--hidden-import", "xlsxwriter",
                "--hidden-import", "core",
                "--hidden-import", "core.compute",
                str(ENTRY_SCRIPT),
            ]

            # Add only essential Qt plugins (platform + basic image formats)
            if qt_plugins_dir and qt_plugins_dir.exists():
                if sys.platform == "darwin":
                    plats = [qt_plugins_dir/"platforms"/"libqcocoa.dylib"]
                    imgs  = [qt_plugins_dir/"imageformats"/"libqico.dylib", qt_plugins_dir/"imageformats"/"libqjpeg.dylib"]
                elif sys.platform.startswith("win"):
                    plats = [qt_plugins_dir/"platforms"/"qwindows.dll"]
                    imgs  = [qt_plugins_dir/"imageformats"/"qico.dll", qt_plugins_dir/"imageformats"/"qjpeg.dll"]
                else:
                    plats = [qt_plugins_dir/"platforms"/"libqxcb.so"]
                    imgs  = [qt_plugins_dir/"imageformats"/"libqico.so", qt_plugins_dir/"imageformats"/"libqjpeg.so"]

                for p in plats + imgs:
                    if p.exists():
                        py_args += ["--add-binary", f"{p}{pathsep}{'PySide6/Qt/plugins/'+str(p.parent.name)}"]

            # Strip symbols on Unix to shrink size a bit
            if sys.platform != "win32":
                py_args.insert(0, "--strip")
            # Optionally, on Windows, user could enable UPX here if desired (not enabled by default)
        else:
            # FULL build: previous behavior with collect-all (safe, larger size)
            py_args = [
                "--noconfirm", "--clean", "--windowed",
                "--name", "qPCR-Calculator",
                "--distpath", str(DIST_DIR),
                "--workpath", str(BUILD_DIR),
                "--specpath", str(BUILD_DIR),
                "--collect-all", "PySide6",
                "--collect-all", "pandas",
                "--collect-all", "openpyxl",
                "--collect-all", "xlsxwriter",
                "--hidden-import", "core",
                "--hidden-import", "core.compute",
                str(ENTRY_SCRIPT),
            ]


        # Icon handling (prefer icon/icon.png; convert per-OS if needed)
        icon_file: Path | None = None
        icon_png = PROJECT_ROOT / "icon" / "icon.png"
        if icon_png.exists():
            if sys.platform == "darwin":
                out_icns = BUILD_DIR / "auto_icon.icns"
                icns = _png_to_icns(icon_png, out_icns)
                if icns:
                    icon_file = icns
            elif sys.platform.startswith("win"):
                out_ico = BUILD_DIR / "auto_icon.ico"
                ico = _png_to_ico(icon_png, out_ico)
                if ico:
                    icon_file = ico
            else:
                icon_file = icon_png

        # Fallback to platform-native icon files if PNG conversion unavailable
        if icon_file is None:
            icon_dir = PROJECT_ROOT / "icon"
            if sys.platform == "darwin":
                alt = icon_dir / "icon.icns"
                if alt.exists():
                    icon_file = alt
            elif sys.platform.startswith("win"):
                alt = icon_dir / "icon.ico"
                if alt.exists():
                    icon_file = alt
            else:
                if icon_png.exists():
                    icon_file = icon_png

        if icon_file:
            py_args += ["--icon", str(icon_file)]
            
        if sys.platform == "darwin":
            py_args[:0] = ["--osx-bundle-identifier", "com.mojack.qpcrcalculator"]
        if args.onefile:
            py_args.insert(0, "--onefile")
        print("[INFO] PyInstaller arguments:")
        print(" ", " ".join(py_args))
        pyim.run(py_args)

        # macOS: if both the .app bundle and a raw executable exist, keep only the .app
        if sys.platform == "darwin":
            app_path = DIST_DIR / "qPCR-Calculator.app"
            raw_exec = DIST_DIR / "qPCR-Calculator"
            try:
                if app_path.exists() and raw_exec.exists():
                    raw_exec.unlink()
                    print("[INFO] Removed standalone UNIX executable; kept .app bundle only.")
            except Exception as e:
                print(f"[WARN] Could not remove standalone executable: {e}")

        try:
            import shutil
            total = 0
            if DIST_DIR.exists():
                for p in DIST_DIR.rglob("*"):
                    if p.is_file():
                        total += p.stat().st_size
            print(f"[INFO] Approx dist size: {total/1024/1024:.1f} MB")
        except Exception:
            pass
        print(f"[OK] Build finished. Output in: {DIST_DIR}")
        if sys.platform == "darwin":
            try:
                import subprocess
                subprocess.run(["open", str(DIST_DIR)], check=False)
            except Exception:
                pass
        sys.exit(0)
    else:
        print("[INFO] Launching qPCR Calculator GUI...")
        # Ensure project root in sys.path
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        try:
            from gui.main_window import main as gui_main
        except Exception as e:
            print("[ERROR] Could not import GUI entry point:", e, file=sys.stderr)
            sys.exit(1)
        sys.exit(gui_main())

if __name__ == "__main__":
    main()
