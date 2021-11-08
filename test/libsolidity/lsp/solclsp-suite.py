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

class ReadPipe(threading.Thread):
    def __init__(self, pipe):
        threading.Thread.__init__(self)
        self.pipe = pipe

    def run(self):
        print("ReadPipe: starting")
        line = self.pipe.readline().decode('utf-8')
        while line:
            print(line)
            line = self.pipe.readline().decode('utf-8')
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

class SolidityLSPTestSuite:
    def main(self):
        self.parse_args_and_prepare()
        self.start_solc_lsp()

        workspace_folders = [
            {'name': 'solidity-lsp', 'uri': self.project_root_uri}
        ]

        traceServer = 'off'
        reply = self.lsp_client.initialize(self.lsp_proc.pid, None, self.project_root_uri, None, LSP_CLIENT_CAPS, traceServer, workspace_folders)
        # Maybe we want to check the init response? Expect certain features to be announced?
        print("reply for initialize(): {}".format(reply))

        reply = self.lsp_client.initialized()
        # Expects reply to be []

        self.run_all_tests()
        self.cleanup()

    def cleanup(self):
        self.lsp_client.shutdown()
        self.lsp_client.exit()

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
            default=os.path.dirname(os.path.realpath(__file__)),
            help='Path to Solidity project\'s root directory (must be fully qualified).',
            nargs="?"
        )
        args = parser.parse_args()

        self.solc_path = args.solc_path
        self.project_root_dir = args.project_root_dir # '/home/trapni/work/solidity/'
        self.project_root_uri = 'file://' + self.project_root_dir
        self.published_diagnostics = []

    def get_test_file_path(self, _test_case_name):
        return "{}/test/libsolidity/lsp/{}.sol".format(self.project_root_dir, _test_case_name)

    def get_test_file_uri(self, _test_case_name):
        return "file://" + self.get_test_file_path(_test_case_name)

    def get_test_file_contents(self, _test_case_name):
        return open(self.get_test_file_path(_test_case_name), "r").read()

    def on_publish_diagnostics(self, _diagnostics):
        print("published diagnostics: {}".format(_diagnostics))
        self.published_diagnostics.append(_diagnostics)
        pass

    def start_solc_lsp(self):
        print("Starting LSP server: {}".format(self.solc_path))

        self.lsp_proc = subprocess.Popen(
            [self.solc_path, "--lsp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        read_pipe = ReadPipe(self.lsp_proc.stderr)
        read_pipe.start()

        lsp_endpoint = pylspclient.LspEndpoint(
            json_rpc_endpoint=pylspclient.JsonRpcEndpoint(
                self.lsp_proc.stdin,
                self.lsp_proc.stdout
            ),
            notify_callbacks={
                'textDocument/publishDiagnostics': lambda x: self.on_publish_diagnostics(x)
            }
        )
        self.lsp_client = pylspclient.LspClient(lsp_endpoint)

    def lsp_open_file(self, _test_case_name):
        version = 1
        file_uri = self.get_test_file_uri(_test_case_name)
        file_contents = self.get_test_file_contents(_test_case_name)
        self.lsp_client.didOpen(pylspclient.lsp_structs.TextDocumentItem(file_uri, SOLIDITY_LANGUAGE_ID, version, file_contents))

    def run_all_tests(self):
        self.test_definition()
        self.test_documentHighlight()
        self.test_hover()
        self.test_implementation()
        self.test_references()
        self.test_signatureHelp()
        self.test_semanticTokensFull()

    def test_definition(self):
        """
        Tests goto-definition. The following tokens can be used to jump from:
        """

        # identifier in expression: `weather`
        TEST_NAME = 'test_definition'
        self.lsp_open_file(TEST_NAME)
        file_uri = self.get_test_file_uri(TEST_NAME)
        print("FILE URI: {}".format(file_uri))
        result = self.lsp_client.definition(
                pylspclient.lsp_structs.TextDocumentIdentifier(file_uri),
                pylspclient.lsp_structs.Position(26, 9))
        print("RESULT RECEIVED IS: {}".format(result))

        # TODO: test on return parameter symbol
        # TODO: test on function parameter symbol
        # TODO: test on enum type symbol in expression
        # TODO: test on enum value symbol in expression
        # TODO: test on import statement to jump to imported file

        os.system("sleep 1") # quick workaround, just wait a bit
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
        #self.lsp_client.signatureHelp(pylspclient.lsp_structs.TextDocumentIdentifier(self.test_file_uri), pylspclient.lsp_structs.Position(14, 4))
        pass

    def test_completion(self):
        # Exemplary code completion test:
        # self.lsp_client.completion(
        #     pylspclient.lsp_structs.TextDocumentIdentifier(self.test_file_uri),
        #     pylspclient.lsp_structs.Position(14, 4),
        #     pylspclient.lsp_structs.CompletionContext(pylspclient.lsp_structs.CompletionTriggerKind.Invoked)
        # )
        pass

if __name__ == "__main__":
    suite = SolidityLSPTestSuite()
    suite.main()
