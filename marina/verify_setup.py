#!/usr/bin/env python3
"""
Pre-flight Checklist for AWG Pulse Optimization System

This script verifies all dependencies, hardware connections, and configuration
before running the optimization system. Run this first to catch issues early.

Usage:
    python verify_setup.py config_forward.ini
    
Output:
    ✓ = OK
    ✗ = Problem (stop and fix)
    ⚠ = Warning (may cause issues)
"""

import sys
import os
import subprocess
from pathlib import Path
from configobj import ConfigObj
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def print_header(title):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def check_mark(condition, message):
    """Print check result."""
    symbol = "✓" if condition else "✗"
    color = "\033[92m" if condition else "\033[91m"  # Green or Red
    reset = "\033[0m"
    status = f"{color}{symbol}{reset}"
    print(f"  {status} {message}")
    return condition


def warn_mark(condition, message):
    """Print warning result."""
    symbol = "⚠" if condition else "✓"
    color = "\033[93m" if condition else "\033[92m"  # Yellow or Green
    reset = "\033[0m"
    status = f"{color}{symbol}{reset}"
    print(f"  {status} {message}")
    return condition


def check_python_version():
    """Verify Python 3.8+."""
    print_header("Python Environment")
    version = sys.version_info
    ok = version >= (3, 8)
    check_mark(ok, f"Python {version.major}.{version.minor}.{version.micro} (need ≥3.8)")
    return ok


def check_python_packages():
    """Verify required packages are installed."""
    print_header("Python Dependencies")
    
    required_packages = {
        'numpy': 'Numerical computing',
        'scipy': 'Scientific computation (signal processing)',
        'pandas': 'Data analysis',
        'matplotlib': 'Plotting',
        'configobj': 'Configuration file parsing',
        'pyvisa': 'VISA hardware control',
    }
    
    optional_packages = {
        'scikit-learn': 'Machine learning utilities',
        'pyserial': 'Serial communication',
        'h5py': 'HDF5 file support',
    }
    
    all_ok = True
    
    # Check required
    for package, description in required_packages.items():
        try:
            __import__(package)
            check_mark(True, f"{package}: {description}")
        except ImportError:
            check_mark(False, f"{package}: {description} [REQUIRED - INSTALL NOW]")
            all_ok = False
    
    # Check optional
    for package, description in optional_packages.items():
        try:
            __import__(package)
            check_mark(True, f"{package}: {description} (optional)")
        except ImportError:
            warn_mark(True, f"{package}: {description} (optional, not installed)")
    
    return all_ok


def check_workspace_structure():
    """Verify the workspace directory structure."""
    print_header("Workspace Structure")
    
    required_dirs = [
        'classes',
        'instruments/agilent_9000',
        'instruments/WX218x',
        'marina',
        'calibrations',
        'configs',
    ]
    
    required_files = [
        'classes/ExperimentalConfigs.py',
        'instruments/agilent_9000.py',
        'instruments/WX218x/awg_control2.py',
    ]
    
    all_ok = True
    
    for dir_path in required_dirs:
        exists = Path(dir_path).exists()
        check_mark(exists, f"Directory: {dir_path}")
        all_ok = all_ok and exists
    
    for file_path in required_files:
        exists = Path(file_path).exists()
        check_mark(exists, f"File: {file_path}")
        all_ok = all_ok and exists
    
    return all_ok


def check_new_modules():
    """Verify new optimization modules exist."""
    print_header("Optimization Modules")
    
    required_files = {
        'marina/pulse_optimizer_core.py': 'Core optimization utilities',
        'marina/optimize_awg_pulse_forward.py': 'Forward optimizer',
        'marina/optimize_awg_pulse_inverted.py': 'Inverted optimizer',
        'marina/config_forward.ini': 'Forward config template',
        'marina/config_inverted.ini': 'Inverted config template',
    }
    
    all_ok = True
    
    for file_path, description in required_files.items():
        exists = Path(file_path).exists()
        check_mark(exists, f"{description}: {file_path}")
        all_ok = all_ok and exists
    
    return all_ok


def check_config_file(config_path):
    """Verify configuration file structure and validity."""
    print_header("Configuration File")
    
    # Check file exists
    config_file = Path(config_path)
    if not check_mark(config_file.exists(), f"Config file exists: {config_path}"):
        return False
    
    try:
        config = ConfigObj(str(config_file))
    except Exception as e:
        check_mark(False, f"Config file parseable: {e}")
        return False
    
    check_mark(True, "Config file parseable")
    
    # Check required sections
    required_sections = ['Hardware', 'Channel', 'Optimization', 'Oscilloscope', 'Measurement', 'Paths']
    all_ok = True
    
    for section in required_sections:
        exists = section in config
        check_mark(exists, f"Section [{section}]")
        all_ok = all_ok and exists
    
    # Check key parameters
    if 'Hardware' in config:
        scope_id = config['Hardware'].get('scope_id')
        check_mark(scope_id, f"Hardware.scope_id set")
    
    if 'Channel' in config:
        channel = config['Channel'].get('channel')
        pulse = config['Channel'].get('pulse_type')
        check_mark(channel and pulse, f"Channel config: channel={channel}, pulse={pulse}")
    
    if 'Optimization' in config:
        amplitude = config['Optimization'].get('amplitude')
        len_awg = config['Optimization'].get('len_awg')
        warn_mark(
            float(amplitude or 0) > 1.0,
            f"Amplitude {amplitude} (typical: 0.1-0.5)"
        )
    
    if 'Measurement' in config:
        num_meas = config['Measurement'].get('num_measurements')
        check_mark(int(num_meas or 0) > 0, f"num_measurements set: {num_meas}")
    
    return all_ok


def check_visa_devices():
    """Try to detect VISA-connected instruments."""
    print_header("VISA Hardware Detection")
    
    try:
        import visa
    except ImportError:
        check_mark(False, "PyVISA installed (required for hardware)")
        return False
    
    try:
        rm = visa.ResourceManager()
        devices = rm.list_resources()
        
        if devices:
            check_mark(True, f"Found {len(devices)} VISA device(s)")
            for device in devices:
                print(f"      • {device}")
            return True
        else:
            warn_mark(True, "No VISA devices detected (hardware not connected?)")
            return False
    
    except Exception as e:
        warn_mark(True, f"VISA enumeration failed: {e}")
        return False


def check_oscilloscope_connection(config_path):
    """Try to connect to Agilent 9000 series oscilloscope."""
    print_header("Oscilloscope Connection")
    
    try:
        config = ConfigObj(str(config_path))
        scope_id = config['Hardware'].get('scope_id')
        
        if not scope_id:
            check_mark(False, "scope_id not configured")
            return False
        
        try:
            from instruments.agilent_9000 import OscilloscopeManager
            
            print(f"  Attempting to connect to Agilent 9000: {scope_id}")
            scope = OscilloscopeManager(scope_id)
            
            connected = scope.is_connected()
            check_mark(connected, f"Oscilloscope connection: {'OK' if connected else 'FAILED'}")
            
            if connected:
                # Try to query identity
                scope.quit()
                return True
            return False
        
        except Exception as e:
            check_mark(False, f"Connection failed: {e}")
            return False
    
    except Exception as e:
        check_mark(False, f"Oscilloscope check failed: {e}")
        return False


def check_calibration_files():
    """Verify theoretical signal files exist."""
    print_header("Calibration Files")
    
    pulse_types = {
        'stokes': 'calibrations/StirapDL_awg/stokes.csv',
        'pump': 'calibrations/StirapDL_awg/pump.csv',
        'P1': 'calibrations/ELYSA_fibre_branch/P1.csv',
        'P2': 'calibrations/ELYSA_fibre_branch/P2.csv',
    }
    
    all_ok = True
    for pulse_type, file_path in pulse_types.items():
        filepath = Path(file_path)
        exists = filepath.exists()
        check_mark(exists, f"{pulse_type}: {file_path}")
        all_ok = all_ok and exists
    
    return all_ok


def check_output_directory(config_path):
    """Verify output directory can be created."""
    print_header("Output Directory")
    
    try:
        config = ConfigObj(str(config_path))
        output_dir = config['Paths'].get('output_dir', './optimization_results')
        
        output_path = Path(output_dir)
        
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            check_mark(True, f"Output directory writable: {output_dir}")
            
            # Try to write a test file
            test_file = output_path / '.test'
            test_file.write_text("test")
            test_file.unlink()
            
            return True
        except Exception as e:
            check_mark(False, f"Cannot write to output directory: {e}")
            return False
    
    except Exception as e:
        check_mark(False, f"Output directory check failed: {e}")
        return False


def main():
    """Run all verification checks."""
    print("\n")
    print("┌" + "─" * 58 + "┐")
    print("│" + " AWG Pulse Optimization - Pre-flight Checklist".center(58) + "│")
    print("└" + "─" * 58 + "┘")
    
    # Get config path from command line
    config_path = sys.argv[1] if len(sys.argv) > 1 else 'config_forward.ini'
    
    checks = [
        ("Python Version", check_python_version),
        ("Python Packages", check_python_packages),
        ("Workspace Structure", check_workspace_structure),
        ("Optimization Modules", check_new_modules),
        ("Config File", lambda: check_config_file(config_path)),
        ("VISA Hardware", check_visa_devices),
        ("Oscilloscope", lambda: check_oscilloscope_connection(config_path)),
        ("Calibration Files", check_calibration_files),
        ("Output Directory", lambda: check_output_directory(config_path)),
    ]
    
    results = {}
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            logger.error(f"Error in {check_name}: {e}")
            results[check_name] = False
    
    # Summary
    print_header("Summary")
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\n  Checks passed: {passed}/{total}\n")
    
    if passed == total:
        print("\n" + "━" * 60)
        print("  ✓ All checks passed! Ready to run optimization.".center(60))
        print("  Run: python optimize_awg_pulse_forward.py")
        print("━" * 60 + "\n")
        return 0
    else:
        print("\n" + "━" * 60)
        print("  ✗ Some checks failed. Fix issues above and retry.".center(60))
        print("━" * 60 + "\n")
        
        failed = [name for name, result in results.items() if not result]
        print("  Failed checks:")
        for name in failed:
            print(f"    • {name}")
        
        print("\n  Recommended fixes:")
        if "Python Packages" in failed:
            print("    pip install numpy scipy pandas matplotlib configobj pyvisa")
        if "Workspace Structure" in failed:
            print("    Check you're in the correct repository root directory")
        if "Oscilloscope" in failed:
            print("    python -c \"import visa; print(visa.ResourceManager().list_resources())\"")
        print()
        
        return 1


if __name__ == '__main__':
    sys.exit(main())
