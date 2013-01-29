'''
    Nereid

    Nereid - Tryton as a web framework

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
import re

from setuptools import setup, Command

class RunTests(Command):
    description = "Run tests"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import sys,subprocess
        errno = subprocess.call([sys.executable, 'tests/__init__.py'])
        raise SystemExit(errno)


class run_audit(Command):
    """Audits source code using PyFlakes for following issues:
        - Names which are used but not defined or used before they are defined.
        - Names which are redefined without having been used.
    """
    description = "Audit source code with PyFlakes"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import os, sys
        try:
            import pyflakes.scripts.pyflakes as flakes
        except ImportError:
            print "Audit requires PyFlakes installed in your system."
            sys.exit(-1)

        warns = 0
        # Define top-level directories
        dirs = ('.')
        for dir in dirs:
            for root, _, files in os.walk(dir):
                if root.startswith(('./build', './doc')):
                    continue
                for file in files:
                    if not file.endswith(('__init__.py', 'upload.py')) \
                            and file.endswith('.py'):
                        warns += flakes.checkPath(os.path.join(root, file))
        if warns > 0:
            print "Audit finished with total %d warnings." % warns
            sys.exit(-1)
        else:
            print "No problems found in sourcecode."
            sys.exit(0)


trytond_module_info = eval(open('__tryton__.py').read())
major_version, minor_version, _ = trytond_module_info.get(
    'version', '0.0.1').split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)

tryton_requires = []
for dep in trytond_module_info.get('depends', []):
    if not re.match(r'(ir|res|workflow|webdav)(\W|$)', dep):
        tryton_requires.append('trytond_%s >= %s.%s, < %s.%s' %
                (dep, major_version, minor_version, major_version,
                    minor_version + 1))


setup(
    name='trytond_nereid',
    version=trytond_module_info.get('version'),
    url='http://nereid.openlabs.co.in/docs/',
    license='GPLv3',
    author='Openlabs Technologies & Consulting (P) Limited',
    author_email='info@openlabs.co.in',
    description='Tryton - Web Framework',
    long_description=__doc__,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Tryton',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],

    install_requires=tryton_requires,
    packages=[
        'trytond.modules.nereid',
        'trytond.modules.nereid.tests',
    ],
    package_dir={
        'trytond.modules.nereid': '.',
        'trytond.modules.nereid.tests': 'tests',
    },
    package_data = {
        'trytond.modules.nereid': trytond_module_info.get('xml', []) \
                + trytond_module_info.get('translation', []) \
                + ['i18n/*.pot', 'i18n/pt_BR/LC_MESSAGES/*'],
    },
    zip_safe=False,
    platforms='any',
    entry_points="""
    [trytond.modules]
    nereid = trytond.modules.nereid
    """,
    tests_require=[
        'mock',
        'pycountry',
    ],
    test_suite='tests',
    test_loader='trytond.test_loader:Loader',
    cmdclass={
        'audit': run_audit,
    },
)
