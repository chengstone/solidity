// SPDX-License-Identifier: GPL-3.0
#include <test/libsolidity/LSPTest.h>
#include <test/Common.h>

#include <libsolidity/lsp/LanguageServer.h>

#include <libsolutil/JSON.h>
#include <libsolutil/CommonIO.h>

#include <range/v3/view/iota.hpp>
#include <boost/filesystem.hpp>

#include <memory>
#include <vector>

using namespace std;
namespace fs = boost::filesystem;

namespace solidity::frontend::test
{

namespace
{

string diff(std::string const& _a, std::string const& _b)
{
	string difftool = getenv("DIFFTOOL") ? getenv("DIFFTOOL") : "";
#if !defined(_WIN32)
	if (difftool.empty())
		difftool = "diff -u";
#endif

	auto const base = fs::unique_path(fs::temp_directory_path() / fs::path("%%%%-%%%%-%%%%-%%%%"));
	auto const a = base.parent_path() / fs::path(base.stem().string() + ".a.json");
	auto const b = base.parent_path() / fs::path(base.stem().string() + ".b.json");

	auto const cleanupFile1 = ScopeGuard{[&] { fs::remove(a); }};
	auto const cleanupFile2 = ScopeGuard{[&] { fs::remove(b); }};

	ofstream(a.generic_string()) << _a;
	ofstream(b.generic_string()) << _b;

	auto const cmdline = fmt::format("{difftool} \"{file1}\" \"{file2}\"",
		fmt::arg("difftool", difftool),
		fmt::arg("file1", a.string()),
		fmt::arg("file2", b.string())
	);

	FILE* fp = ::popen(cmdline.c_str(), "r");
	if (!fp)
		return "";
	auto const cleanupStdoutHandle = ScopeGuard{[&] { pclose(fp); }};

	ostringstream output;
	char buf[32] = {0};
	size_t n = 0;
	while ((n = fread(buf, 1, sizeof(buf), fp)) > 0)
		output << string_view(buf, n);
	return output.str();
}

class MockTransport: public lsp::Transport
{
public:
	std::function<void()> onClose = []{};

	explicit MockTransport(std::vector<Json::Value> _requests):
		m_requests{std::move(_requests)}
	{}

	std::vector<Json::Value> const& requests() const noexcept { return m_replies; }
	std::vector<Json::Value> const& replies() const noexcept { return m_replies; }

	bool closed() const noexcept override
	{
		return m_readOffset >= m_requests.size();
	}

	std::optional<Json::Value> receive() override
	{
		if (m_readOffset < m_requests.size())
		{
			Json::Value value = m_requests.at(m_readOffset++);
			tracelog(
				"MockTransport Client -> Server: {}/{}\n\033[32m{}\033[m\n",
				m_readOffset,
				m_requests.size(),
				jsonPrettyPrint(value)
			);
			if (m_readOffset == m_requests.size())
				m_terminate();
			return value;
		}
		return nullopt;
	}

	void notify(std::string const& _method, Json::Value const& _params) override
	{
		Json::Value json;
		json["method"] = _method;
		json["params"] = _params;
		send(json);
	}

	void reply(lsp::MessageID _id, Json::Value const& _message) override
	{
		Json::Value json;
		json["result"] = _message;
		send(json, _id);
	}

	void error(lsp::MessageID _id, lsp::ErrorCode _code, std::string const& _message) override
	{
		Json::Value json;
		json["error"]["code"] = static_cast<int>(_code);
		json["error"]["message"] = _message;
		send(json, _id);
	}

private:
	void send(Json::Value _json, lsp::MessageID _id = Json::nullValue)
	{
		_json["jsonrpc"] = "2.0";
		if (!_id.isNull())
			_json["id"] = _id;

		tracelog("MockTransport Server -> Client:\n\033[36m{}\033[m\n", jsonPrettyPrint(_json));
		m_replies.push_back(_json);
	}

	template <typename... Args>
	void tracelog(Args... _args)
	{
		//if (getenv("TRACE") && *getenv("TRACE") != '0')
		fmt::print(std::forward<Args>(_args)...);
	}

private:
	std::vector<Json::Value> m_requests;
	size_t m_readOffset = 0;
	std::vector<Json::Value> m_replies;
	std::function<void()> m_terminate = []{};
};

void lspTestCase(fs::path _testCaseFile)
{
	try
	{
		auto testCase = std::make_unique<LSPTest>(_testCaseFile);
		stringstream errorStream;
		switch (testCase->run(errorStream))
		{
		case TestCase::TestResult::Success:
			break;
		case TestCase::TestResult::Failure:
			BOOST_ERROR("Test expectation mismatch.\n" + errorStream.str());
			break;
		case TestCase::TestResult::FatalError:
			BOOST_ERROR("Fatal error during test.\n" + errorStream.str());
			break;
		}
	}
	catch (boost::exception const& _e)
	{
		BOOST_ERROR("Exception during extracted test: " << boost::diagnostic_information(_e));
	}
	catch (std::exception const& _e)
	{
		BOOST_ERROR("Exception during extracted test: " << boost::diagnostic_information(_e));
	}
	catch (...)
	{
		BOOST_ERROR("Unknown exception during extracted test: " << boost::current_exception_diagnostic_information());
	}
}

} // end anonymous namespace

LSPTest::LSPTest(fs::path _path): m_path{std::move(_path)}
{
}

LSPTest::TestResult LSPTest::run(std::ostream& _output)
{
	auto const fileContents = util::readFileAsString(m_path);
	std::string errorString;
	Json::Value json;
	if (!util::jsonParseStrict(fileContents, json, &errorString))
	{
		_output << errorString;
		return TestResult::FatalError;
	}
	if (!json.isArray())
	{
		_output << "JSON format error. Top level element must be an array.\n";
		return TestResult::FatalError;
	}

	std::vector<Json::Value> requests;
	std::vector<Json::Value> expectedReplies;

	for (auto const i: ranges::views::iota(0, static_cast<int>(json.size())))
	{
		requests.push_back(json[i]["request"]);
		if (Json::Value output = json[i]["response"]; output.isArray())
			for (int k = 0; k < static_cast<int>(output.size()); ++k)
				expectedReplies.push_back(output[k]);
	}

	lsp::LanguageServer lsp([](auto) {} /* debug log */, make_unique<MockTransport>(requests));
	MockTransport& transport = static_cast<MockTransport&>(lsp.transport());
	transport.onClose = [&lsp] { lsp.terminate(); };

	lsp.run();

	vector<Json::Value> const& replies = transport.replies();
	for (auto const i: ranges::views::iota(0u, min(replies.size(), expectedReplies.size())))
	{
		Json::Value actualReply = replies[i];
		Json::Value expectedReply = expectedReplies[i];
		auto const actualText = jsonPrettyPrint(actualReply);
		auto const expectedText = jsonPrettyPrint(expectedReply);
		if (actualText != expectedText)
		{
			auto const diffMessage = diff(expectedText, actualText);
			if (!diffMessage.empty())
				_output << "Test " << i << " failed expectation in reply.\n" << diffMessage << '\n';
			else
				_output <<
					"Test " << i << " failed reply expectation.\n" <<
					"Expected:\n" << expectedText << '\n' <<
					"Actual:\n" << actualText << '\n';
			return TestResult::Failure;
		}
	}

	if (replies.size() != expectedReplies.size())
	{
		_output << fmt::format(
			"Expected {expected} number of replies from LSP but got {actual}.\n",
			fmt::arg("expected", expectedReplies.size()),
			fmt::arg("actual", replies.size())
		);
		return TestResult::Failure;
	}

	return TestResult::Success;
}

int LSPTest::registerTestCases(boost::unit_test::test_suite& _suite)
{
	auto const& options = solidity::test::CommonOptions::get();
	return registerTestCases(_suite, options.testPath, fs::path("libsolidity") / "lsp");
}

int LSPTest::registerTestCases(
	boost::unit_test::test_suite& _suite,
	fs::path const& _basePath,
	fs::path const& _path
)
{
	fs::path const fullPath = _basePath / _path;
	int numTestsAdded = 0;

	if (fs::is_directory(fullPath))
	{
		boost::unit_test::test_suite* subTestSuite = BOOST_TEST_SUITE(_path.filename().string());
		for (auto const& entry: boost::iterator_range<fs::directory_iterator>(
			fs::directory_iterator(fullPath),
			fs::directory_iterator()
		))
		{
			auto const pathToChild = entry.path();
			if ((fs::is_regular_file(pathToChild) && pathToChild.extension().string() == ".json") ||
				fs::is_directory(pathToChild)
			)
			{
				numTestsAdded += registerTestCases(
					*subTestSuite,
					_basePath,
					_path / entry.path().filename()
				);
			}
		}
		_suite.add(subTestSuite);
	}
	else
	{
		// This must be a vector of unique_ptrs because Boost.Test keeps the equivalent of a string_view to the filename
		// that is passed in. If the strings were stored directly in the vector, pointers/references to them would be
		// invalidated on reallocation.
		static vector<unique_ptr<string const>> filenames;
		filenames.emplace_back(make_unique<string>(_path.string()));
		auto const testCaseName = (_path.parent_path() / _path.stem()).string(); // strip off file extension
		auto testCase = boost::unit_test::make_test_case(
			[fullPath] { BOOST_REQUIRE_NO_THROW({ lspTestCase(fullPath); }); },
			_path.stem().string(), // test-case name
			*filenames.back(),     // test-case file name
			0                      // test-case line number
		);
		_suite.add(testCase);
	}
	return numTestsAdded;
}

}
