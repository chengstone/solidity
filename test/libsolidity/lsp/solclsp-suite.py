#!/usr/bin/env python3

# DEPENDENCIES:
#     pip install git+https://github.com/yeger00/pylspclient.git --user

# NOTES
# YESTERDAY
# - improved semantic tokens highlighting coverage
# TODAY
# - (TRYING TO FINISH) natspec/signature: missing cases, trying to get the natspec-tooltip formatted
#
# - work on test suite via python

import pylspclient
import subprocess
import threading
import argparse
import os
from typing import List
from deepdiff import DeepDiff
from pprint import pprint

SGR_RESET = '\033[m'
SGR_TEST_BEGIN = '\033[1;33m'
SGR_STATUS_OKAY = '\033[1;32m'
SGR_STATUS_FAIL = '\033[1;31m'
SGR_INSPECT = '\033[1;35m'

TEST_NAME = 'test_definition'

class ReadPipe(threading.Thread):
    """
        Used to link (solc) process stdio.
    """
    def __init__(self, pipe):
        threading.Thread.__init__(self)
        self.pipe = pipe

    def run(self):
        try:
            print("ReadPipe: starting")
            line = self.pipe.readline().decode('utf-8')
            while line:
                print(line)
                #print("\033[1;42m{}\033[m\n".format(line))
                line = self.pipe.readline().decode('utf-8')
        except Exception as e:
            print("ReadPipe: Unhandled exception: {}\n".format(e))
        finally:
            print("ReadPipe: terminating")

SOLIDITY_LANGUAGE_ID = "solidity" # pylspclient.lsp_structs.LANGUAGE_IDENTIFIER.C

LSP_CLIENT_CAPS = {
        'textDocument': {'codeAction': {'dynamicRegistration': True},
        'codeLens': {'dynamicRegistration': True},
        'colorProvider': {'dynamicRegistration': True},
        'completion': {'completionItem': {'commitCharactersSupport': True,
            'documentationFormat': ['markdown', 'plaintext'],
            'snippetSupport': True},
        'completionItemKind': {'valueSet': [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
            17, 18, 19, 20, 21, 22, 23, 24, 25
        ]},
        'contextSupport': True,
        'dynamicRegistration': True},
        'definition': {'dynamicRegistration': True},
        'documentHighlight': {'dynamicRegistration': True},
        'documentLink': {'dynamicRegistration': True},
        'documentSymbol': {
            'dynamicRegistration': True,
            'symbolKind': {'valueSet': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
                17, 18, 19, 20, 21, 22, 23, 24, 25, 26
            ]}
        },
        'formatting': {'dynamicRegistration': True},
        'hover': {'contentFormat': ['markdown', 'plaintext'],
        'dynamicRegistration': True},
        'implementation': {'dynamicRegistration': True},
        'onTypeFormatting': {'dynamicRegistration': True},
        'publishDiagnostics': {'relatedInformation': True},
        'rangeFormatting': {'dynamicRegistration': True},
        'references': {'dynamicRegistration': True},
        'rename': {'dynamicRegistration': True},
        'signatureHelp': {'dynamicRegistration': True,
        'signatureInformation': {'documentationFormat': ['markdown', 'plaintext']}},
        'synchronization': {'didSave': True,
        'dynamicRegistration': True,
        'willSave': True,
        'willSaveWaitUntil': True},
        'typeDefinition': {'dynamicRegistration': True}},
        'workspace': {'applyEdit': True,
        'configuration': True,
        'didChangeConfiguration': {'dynamicRegistration': True},
        'didChangeWatchedFiles': {'dynamicRegistration': True},
        'executeCommand': {'dynamicRegistration': True},
        'symbol': {
            'dynamicRegistration': True,
            'symbolKind': {'valueSet': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26 ]}
        },
        'workspaceEdit': {'documentChanges': True},
        'workspaceFolders': True}
    }

class SolcInstance:
    """
    Manages the solc executable instance and provides the handle to communicate with it
    """

    process: subprocess.Popen
    endpoint: pylspclient.LspEndpoint
    client: pylspclient.LspClient
    #published_diagnostics: object

    def __init__(self, _solc_path: str) -> None:
        self.solc_path = _solc_path
        self.published_diagnostics = []
        self.client = pylspclient.LspClient(None)

    def __enter__(self):
        print("Starting solc LSP instance: {}".format(self.solc_path))
        self.process = subprocess.Popen(
            [self.solc_path, "--lsp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.read_pipe = ReadPipe(self.process.stderr)
        self.read_pipe.start()
        self.endpoint = pylspclient.LspEndpoint(
            json_rpc_endpoint=pylspclient.JsonRpcEndpoint(
                self.process.stdin,
                self.process.stdout
            ),
            notify_callbacks={
                'textDocument/publishDiagnostics': lambda x: self.on_publish_diagnostics(x)
            }
        )
        self.client = pylspclient.LspClient(self.endpoint)
        return self

    def __exit__(self, _exception_type, _exception_value, _traceback) -> None:
        print("Stopping solc instance.\n")
        self.client.shutdown()
        self.client.exit()
        self.read_pipe.join()

    def on_publish_diagnostics(self, _diagnostics) -> None:
        print("published diagnostics: {}".format(_diagnostics))
        self.published_diagnostics.append(_diagnostics)

class SolcTests:
    def __init__(self, _client: SolcInstance, _project_root_dir: str):
        self.solc = _client
        self.project_root_dir = _project_root_dir
        self.project_root_uri = 'file://' + self.project_root_dir
        self.tests = 0
        print("root dir: {}\n".format(self.project_root_dir))

    # {{{ helpers
    def get_test_file_path(self, _test_case_name):
        return "{}/test/libsolidity/lsp/{}.sol".format(self.project_root_dir, _test_case_name)

    def get_test_file_uri(self, _test_case_name):
        return "file://" + self.get_test_file_path(_test_case_name)

    def get_test_file_contents(self, _test_case_name):
        return open(self.get_test_file_path(_test_case_name), "r").read()

    def lsp_open_file(self, _test_case_name):
        version = 1
        file_uri = self.get_test_file_uri(_test_case_name)
        file_contents = self.get_test_file_contents(_test_case_name)
        self.solc.client.didOpen(pylspclient.lsp_structs.TextDocumentItem(
            file_uri, SOLIDITY_LANGUAGE_ID, version, file_contents
        ))

    def expect(self, _cond: bool, _description: str) -> None:
        self.tests = self.tests + 1
        prefix = "[{}] ".format(self.tests)
        if _cond:
            print(prefix + SGR_TEST_BEGIN + _description + SGR_RESET + ': ' + SGR_STATUS_OKAY + 'OK' + SGR_RESET)
        else:
            print(prefix + SGR_TEST_BEGIN + _description + SGR_RESET + ': ' + SGR_STATUS_FAIL + 'FAILED' + SGR_RESET)
            os._exit(1)

    def expect_equal(self, _description: str, _actual, _expected) -> None:
        self.tests = self.tests + 1
        prefix = "[{}] ".format(self.tests) + SGR_TEST_BEGIN + _description + ': '
        diff = DeepDiff(_actual, _expected)
        if len(diff) == 0:
            print(prefix + SGR_STATUS_OKAY + 'OK' + SGR_RESET)
            return

        print(prefix + SGR_STATUS_FAIL + 'FAILED' + SGR_RESET)
        pprint(diff)
        raise RuntimeError('Expectation failed.')

    def inspect(self, _msg: str, _obj: object) -> None:
        print("{}Inspect {}: {}{}".format(SGR_INSPECT, _msg, SGR_RESET, _obj))

    # }}}

    # {{{ actual tests
    def run(self):
        self.open_files_and_test_publish_diagnostics()
        self.test_definition()
        # self.test_documentHighlight()
        # self.test_hover()
        # self.test_implementation()
        # self.test_references()
        # self.test_signatureHelp()
        # self.test_semanticTokensFull()

    def extract_test_file_name(self, _uri: str):
        """
        Extracts the project-root URI prefix from the URI.
        """
        subLength = len(self.project_root_uri)
        return _uri[subLength:]

    def open_files_and_test_publish_diagnostics(self):
        self.lsp_open_file(TEST_NAME)

        os.system('sleep 1') # TODO: wait_until_notification('published_diagnostics')

        # should have received one published_diagnostics notification
        print("-- len: {}".format(len(self.solc.published_diagnostics)))
        self.expect(len(self.solc.published_diagnostics) == 1, "one published_diagnostics message")
        published_diagnostics = self.solc.published_diagnostics[0]

        self.expect(published_diagnostics['uri'] == self.get_test_file_uri(TEST_NAME), 'diagnostic: uri')

        # containing one single diagnotics report
        diagnostics = published_diagnostics['diagnostics']
        self.expect(len(diagnostics) == 1, "one diagnostics")
        self.inspect('diagnostic', diagnostics)
        diagnostic = diagnostics[0]
        self.expect(diagnostic['code'] == 3805, 'diagnostic: pre-release compiler')
        self.expect_equal('check range', diagnostic['range'], {'end': {'character': 0, 'line': 0}, 'start': {'character': 0, 'line': 0}})

    def test_definition(self):
        """
        Tests goto-definition. The following tokens can be used to jump from:
        """

        self.solc.published_diagnostics.clear()


        # identifier in expression: `weather` in assignment
        result = self.solc.client.definition(
                pylspclient.lsp_structs.TextDocumentIdentifier(self.get_test_file_uri(TEST_NAME)),
                pylspclient.lsp_structs.Position(24, 9))
        print("RESULT RECEIVED IS: {}".format(result))

        # TODO: test on return parameter symbol
        # TODO: test on function parameter symbol
        # TODO: test on enum type symbol in expression
        # TODO: test on enum value symbol in expression
        # TODO: test on import statement to jump to imported file

        # HACK: WIP
        #os.system("sleep 1") # quick workaround, just wait a bit
        pass

    def test_implementation(self):
        # TODO
        pass

    def test_documentHighlight(self):
        # TODO
        pass

    def test_references(self):
        # TODO: i.g. find all references
        pass

    def test_hover(self):
        # TODO: e.g. this shows NatSpec doc and signature
        pass

    def test_semanticTokensFull(self):
        # TODO: that's the semantic syntax highglihting feature
        # It returns the descriptions for the entire file.
        pass

    def test_signatureHelp(self):
        #self.solc.client.signatureHelp(pylspclient.lsp_structs.TextDocumentIdentifier(self.test_file_uri), pylspclient.lsp_structs.Position(14, 4))
        pass

    def test_completion(self):
        # Exemplary code completion test:
        # self.solc.client.completion(
        #     pylspclient.lsp_structs.TextDocumentIdentifier(self.test_file_uri),
        #     pylspclient.lsp_structs.Position(14, 4),
        #     pylspclient.lsp_structs.CompletionContext(pylspclient.lsp_structs.CompletionTriggerKind.Invoked)
        # )
        pass
    # }}}

class SolidityLSPTestSuite:
    def main(self):
        self.parse_args_and_prepare()

        with SolcInstance(self.solc_path) as solc:
            project_root_uri = 'file://' + self.project_root_dir
            workspace_folders = [ {'name': 'solidity-lsp', 'uri': project_root_uri} ]
            traceServer = 'off'
            solc.client.initialize(solc.process.pid, None, project_root_uri, None, LSP_CLIENT_CAPS, traceServer, workspace_folders)
            solc.client.initialized()
            # Maybe we want to check the init response? Expect certain features to be announced?

            tests = SolcTests(solc, self.project_root_dir)
            tests.run()

    def parse_args_and_prepare(self):
        parser = argparse.ArgumentParser(description='Solidity LSP Test suite')
        parser.add_argument(
            'solc_path',
            type=str,
            default="/home/trapni/work/solidity/build/solc/solc",
            help='Path to solc binary to test against',
            nargs="?"
        )
        parser.add_argument(
            'project_root_dir',
            type=str,
            default="{}/../../..".format(os.path.dirname(os.path.realpath(__file__))),
            help='Path to Solidity project\'s root directory (must be fully qualified).',
            nargs="?"
        )
        args = parser.parse_args()

        self.solc_path = args.solc_path
        self.project_root_dir = os.path.realpath(args.project_root_dir) # '/home/trapni/work/solidity/'

if __name__ == "__main__":
    suite = SolidityLSPTestSuite()
    suite.main()
