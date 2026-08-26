import os
import zipfile

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_DIR = os.path.join(ROOT_DIR, "target")
PACKAGE_NAME = "configurable_duplicate_fields"

INCLUDED_TOP_LEVEL = ["__init__.py", "manifest.json", "config.json"]


def add_file(archive, path):
    archive.write(path, os.path.relpath(path, ROOT_DIR))


def main():
    os.makedirs(TARGET_DIR, exist_ok=True)
    output_path = os.path.join(TARGET_DIR, PACKAGE_NAME + ".ankiaddon")

    package_dir = os.path.join(ROOT_DIR, PACKAGE_NAME)
    package_files = []
    for dirpath, dirnames, filenames in os.walk(package_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            if filename.endswith(".pyc"):
                continue
            package_files.append(os.path.join(dirpath, filename))

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in INCLUDED_TOP_LEVEL:
            add_file(archive, os.path.join(ROOT_DIR, name))
        for path in sorted(package_files):
            add_file(archive, path)

    print("Created %s" % output_path)


if __name__ == "__main__":
    main()
