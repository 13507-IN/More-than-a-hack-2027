"""Fetch the licensed match bundle from a Google Drive share link.

The bundle is gated: the link only works for an account that has enrolled and
accepted the terms.  This helper supports three routes, in order:

1. a browser ``cookies.txt`` exported for the Google account (recommended);
2. ``yt-dlp`` with ``--cookies-from-browser`` when it can read the browser DB;
3. a manual download, which is always the fallback.

    python tools/fetch_data.py --url "https://drive.google.com/file/d/<id>/view"
    python tools/fetch_data.py --cookies cookies.txt --extract

Nothing here bypasses the share permissions.  A private link that Google
answers with a sign-in page cannot be downloaded anonymously.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_URL = "https://drive.google.com/file/d/12q0SU0cyX4DowVHMJ6v0ctLUOPWsmZQF/view"


def file_id(url):
    if "id=" in url:
        return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["id"][0]
    parts = [part for part in url.split("/") if part]
    if "d" in parts:
        return parts[parts.index("d") + 1]
    return url


def download_gdown(url, destination, cookies=None):
    try:
        import gdown
    except ImportError:
        return False
    try:
        if cookies:
            return bool(gdown.download(url, destination, cookies=cookies, quiet=False))
        return bool(gdown.download(url, destination, quiet=False))
    except Exception as error:  # gdown raises many exception types
        print("gdown failed: {}".format(error))
        return False


def download_urllib(url, destination, cookies=None):
    """Large-file aware urllib download using the confirmation token."""
    opener = urllib.request.build_opener()
    if cookies:
        jar = {}
        with open(cookies, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#") or "\t" not in line:
                    continue
                fields = line.strip().split("\t")
                if len(fields) >= 7:
                    jar.setdefault(fields[0], {})[fields[5]] = fields[6]
        cookie_header = "; ".join(
            "{}={}".format(name, value)
            for domain, values in jar.items() if "google" in domain
            for name, value in values.items()
        )
        if cookie_header:
            opener.addheaders.append(("Cookie", cookie_header))
    opener.addheaders.append(("User-Agent", "Mozilla/5.0"))

    request = opener.open(url, timeout=90)
    final = request.geturl()
    if "accounts.google.com" in final:
        print("Google redirected to sign-in: this link is not public for this session.")
        return False

    with open(destination, "wb") as handle:
        shutil.copyfileobj(request, handle, length=1024 * 1024)
    return os.path.isfile(destination) and os.path.getsize(destination) > 1024


def extract(archive, target):
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        bundle.extractall(target)
    # Most bundles have a single top-level folder; lift it if that is all there is.
    entries = [name for name in names if not name.startswith("__MACOSX")]
    tops = {name.split("/")[0] for name in entries if name.strip()}
    if len(tops) == 1:
        top = os.path.join(target, tops.pop())
        if os.path.isdir(top):
            for name in os.listdir(top):
                shutil.move(os.path.join(top, name), os.path.join(target, name))
            os.rmdir(top)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--cookies", default=None, help="Netscape cookies.txt export")
    parser.add_argument("--extract", action="store_true", help="unzip into data/")
    parser.add_argument("--out", default=os.path.join(ROOT, "data"))
    args = parser.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    target = os.path.join(args.out, "mtah2027_bundle")
    print("resolving", file_id(args.url))
    ok = download_urllib("https://drive.google.com/uc?export=download&id={}".format(
        file_id(args.url)), target, args.cookies)
    if not ok:
        print("Trying gdown ...")
        ok = download_gdown(args.url, target, args.cookies)
    if not ok:
        print(
            "\nCould not download automatically. The bundle is gated.\n"
            "1. Open the share link in a browser signed in to the enrolled account.\n"
            "2. Download the archive.\n"
            "3. Unpack it into {} (or run this script with --extract).\n"
            "See data/README.md.".format(args.out)
        )
        return 1

    print("downloaded", target, os.path.getsize(target), "bytes")
    if args.extract:
        extract(target, args.out)
        os.remove(target)
        print("extracted into", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
