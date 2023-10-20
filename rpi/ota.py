import microcontroller
import adafruit_requests as requests
import adafruit_hashlib as hashlib


GIT_BASE = 'https://github.com/kgutwin/laundrymon'
CODE_PATH = 'rpi/main.py'


def tagfile_read():
    with open('/code/latest') as fp:
        return fp.read()

def tagfile_write(tag):
    with open('/code/latest', 'w') as fp:
        fp.write(tag)

def run_latest():
    tag = tagfile.read()
    __import__(f'code.{tag}')


def fetch_version(git_hash, md5_hash):
    url = f'{GIT_BASE}/raw/{git_hash}/{CODE_PATH}'
    response = requests.get(url)

    fn = f'/code/{git_hash}.py'
    with open(fn, 'w') as fp:
        for chunk in response.iter_content(32768):
            fp.write(chunk)

    # verify
    m = hashlib.md5()
    with open(fn) as fp:
        while chunk := fp.read(32768):
            m.update(chunk)
    if m.hexdigest() != md5_hash:
        raise ValueError('hash does not match')

    return fn


def update_to(target):
    current_hash = tagfile_read()
    old_fn = f'/code/{current_hash}.py'

    # fetch and verify the new version
    new_fn = fetch_version(target['git_hash'], target['md5_hash'])

    # no exception means we're good, update the tagfile
    tagfile_write(target['git_hash'])

    # clean out excessive old revisions

    # reset
    microcontroller.reset()
