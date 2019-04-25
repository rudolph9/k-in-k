#!/usr/bin/env python3

from kninja import *
import sys
import os.path
import functools

# Project Definition
# ==================

proj = KProject()

# Executing Kore using the Kore backend
# -------------------------------------

kore_from_config = proj.rule( 'kore-from-config'
                            , description = 'Extracting <kore> cell'
                            , command = 'lib/kore-from-config "$cell" "$in" "$out"'
                            , ext = 'kore'
                            )
def kore_exec(kore, ext = 'kore-exec'):
    return proj.rule( 'kore-exec'
                    , description = 'kore-exec'
                    , command     = '$k_bindir/kore-exec $kore --module "$module" --pattern $in > $out'
                    ) \
                    .variables(kore = kore) \
                    .implicit([kore, proj.build_k('haskell')])

# Parsing Outer K using k-light
# -----------------------------

def build_k_light():
    return proj.rule( 'build-k-light'
                    , description = 'Building K'
                    , command = 'cd ext/k-light && mvn package -q -DskipTests'
                    ) \
                    .output('ext/k-light/bin/kompile')
k_light = proj.dotTarget().then(build_k_light())

# Kore to K Pipeline
# ------------------

ekore  = 'src/ekore.md'
kore   = 'src/kore.md'
parser = 'src/parser-util.md'
file   = 'src/file-util.md'

kink  = proj.definition( backend   = 'java'
                       , main      = 'src/kink.md'
                       , other     = [kore, ekore, parser, file]
                       , directory = proj.builddir('kink')
                       , flags     = '--syntax-module KINK-SYNTAX'
                       , alias     = 'kink'
                       )

def pipeline(pipeline, extension):
    return kink.krun().variables(flags = '"-cPIPELINE=%s"' %(pipeline))

def kink_test(base_dir, test_file, pipeline):
    input = os.path.join(base_dir, test_file)
    expected = os.path.join(base_dir, 'expected.ekore')
    return proj.source(input) \
               .then(pipeline) \
               .then(kore_from_config.variables(cell = 'definition')) \
               .then(proj.check(proj.source(expected))
                         .variables(flags = '--ignore-all-space --ignore-blank-lines')) \
               .default()

ekore_test    = functools.partial(kink_test, pipeline = pipeline('#ekorePipeline'   , 'ekorePipeline'))

def parse_test(base_dir, def_file, input_program):
    def_path = os.path.join(base_dir, def_file)
    prog_path = os.path.join(base_dir, 'programs', input_program)
    expected = prog_path + '.kast'
    return proj.source(def_path) \
               .then(pipeline('#kastPipeline(\\"' + prog_path + '\\")'
                             , 'parse-' + input_program
                             ).implicit([prog_path])) \
               .then(kore_from_config.variables(cell = 'k')) \
               .then(proj.check(proj.source(expected))
                         .variables(flags = '--ignore-all-space --ignore-blank-lines')) \
               .default()

def lang_test(base_dir, module, program):
    language_kore    = os.path.join(base_dir, 'expected.ekore')
    program_pattern  = os.path.join(base_dir, 'programs', program + '.kast')
    expected_pattern = os.path.join(base_dir, 'programs', program + '.expected')
    runWithHaskell_pipeline = pipeline('#runWithHaskellBackendPipeline', 'noFrontend')

    lang_no_frontend_kore =  proj.source(language_kore) \
                                 .then(runWithHaskell_pipeline \
                                          .ext('noFrontend')) \
                                 .then(kore_from_config.variables(cell = 'definition'))
    return proj.source(program_pattern).then(kore_exec(lang_no_frontend_kore)
                                                 .ext('kore-exec')
                                                 .variables(module = module)
                                            ) \
                                       .then(proj.check(expected_pattern) \
                                                 .variables(flags = '--ignore-all-space --ignore-blank-lines')) \
                                       .default()

# Foobar
foobar_tests = []
foobar_tests += [ ekore_test('t/foobar', 'foobar.ekore')            ]
foobar_tests += [ ekore_test('t/foobar', 'expected.ekore')          ]
foobar_tests += [ parse_test('t/foobar', 'foobar.k', 'bar.foobar')  ]
foobar_tests += [ lang_test('t/foobar', 'FOOBAR', 'bar.foobar')     ]
proj.build('t/foobar', 'phony', inputs = Target.to_paths(foobar_tests))

# Peano
peano_tests = []
peano_tests += [ ekore_test('t/peano', 'peano.ekore')    ]
peano_tests += [ ekore_test('t/peano', 'expected.ekore') ]
peano_tests += [ lang_test('t/peano', 'PEANO', 'two-plus-two.peano') ]
peano_tests += [ parse_test('t/peano', 'peano.k', 'two-plus-two.peano') ]
proj.build('t/peano', 'phony', inputs = Target.to_paths(peano_tests))

# Unit tests
# ==========

proj.source('unit-tests.md') \
    .then(proj.rule_tangle().output(proj.tangleddir('unit-tests-spec.k'))) \
    .then(kink.kprove()) \
    .alias('unit-tests')
