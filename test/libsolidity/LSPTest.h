// SPDX-License-Identifier: GPL-3.0
#pragma once

#include <test/TestCase.h>
#include <boost/filesystem/path.hpp>
#include <boost/test/unit_test.hpp>

#include <iosfwd>
#include <memory>
#include <string>
#include <vector>

namespace solidity::frontend::test
{

class LSPTest
{
public:
	using TestResult = solidity::frontend::test::TestCase::TestResult;

	explicit LSPTest(boost::filesystem::path _testCaseFile);

	TestResult run(std::ostream& _stream);

	static int registerTestCases(boost::unit_test::test_suite& _suite);

private:
	static int registerTestCases(
		boost::unit_test::test_suite& _suite,
		boost::filesystem::path const& _basePath,
		boost::filesystem::path const& _path
	);

	boost::filesystem::path m_path;
};

}
