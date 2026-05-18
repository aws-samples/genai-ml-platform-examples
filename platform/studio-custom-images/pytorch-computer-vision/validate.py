#!/usr/bin/env python3
"""Verify that all computer vision packages are installed correctly."""

import sys


def check_package(name, import_name=None):
    if import_name is None:
        import_name = name.replace("-", "_")
    try:
        module = __import__(import_name)
        version = getattr(module, "__version__", "unknown")
        print(f"  [OK] {name}: {version}")
        return True
    except ImportError as e:
        print(f"  [FAIL] {name}: {e}")
        return False


def main():
    print("=" * 50)
    print("PyTorch Computer Vision Image Validation")
    print("=" * 50)

    ok = True

    print("\n[Base image packages]")
    ok &= check_package("torch")
    ok &= check_package("cv2", "cv2")
    ok &= check_package("numpy")
    ok &= check_package("pandas")

    print("\n[Added packages]")
    ok &= check_package("albumentations")
    ok &= check_package("timm")
    ok &= check_package("ultralytics")

    print("\n" + "=" * 50)
    if ok:
        print("VALIDATION PASSED")
        return 0
    else:
        print("VALIDATION FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
