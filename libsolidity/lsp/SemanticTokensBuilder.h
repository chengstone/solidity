/*
	This file is part of solidity.

	solidity is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	solidity is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with solidity.  If not, see <http://www.gnu.org/licenses/>.
*/
// SPDX-License-Identifier: GPL-3.0
#include <libsolidity/ast/AST.h>
#include <libsolidity/ast/ASTVisitor.h>
#include <jsoncpp/json/json.h>

#include <fmt/format.h>

namespace solidity::langutil
{
class CharStream;
struct SourceLocation;
}

namespace solidity::lsp
{

// See: https://microsoft.github.io/language-server-protocol/specifications/specification-3-17/#semanticTokenTypes
enum class SemanticTokenType
{
	Class,
	Comment,
	Enum,
	EnumMember,
	Event,
	Function,
	Interface,
	Keyword,
	Macro,
	Method,
	Modifier,
	Number,
	Operator,
	Parameter,
	Property,
	String,
	Struct,
	Type,
	TypeParameter,
	Variable,

	// Unused below:
	// Namespace,
	// Regexp,
};

enum class SemanticTokenModifiers
{
	None            = 0,

	// Member integer values must be bit-values as
	// they can be OR'd together.
	Abstract        = 0x0001,
	Declaration     = 0x0002,
	Definition      = 0x0004,
	Deprecated      = 0x0008,
	Documentation   = 0x0010,
	Modification    = 0x0020,
	Readonly        = 0x0040,

	// Unused below:
	// Static,
	// Async,
	// DefaultLibrary,
};

constexpr SemanticTokenModifiers operator|(SemanticTokenModifiers a, SemanticTokenModifiers b) noexcept
{
	return static_cast<SemanticTokenModifiers>(static_cast<int>(a) | static_cast<int>(b));
}

class SemanticTokensBuilder: public frontend::ASTConstVisitor
{
public:
	Json::Value build(frontend::SourceUnit const& _sourceUnit, langutil::CharStream const& _charStream);

	void reset(langutil::CharStream const* _charStream);
	void encode(
		langutil::SourceLocation const& _sourceLocation,
		SemanticTokenType _tokenType,
		SemanticTokenModifiers _modifiers = SemanticTokenModifiers::None
	);

	bool visit(frontend::ContractDefinition const&) override;
	bool visit(frontend::ElementaryTypeName const&) override;
	bool visit(frontend::ElementaryTypeNameExpression const&) override;
	bool visit(frontend::EnumDefinition const&) override;
	bool visit(frontend::EnumValue const&) override;
	bool visit(frontend::ErrorDefinition const&) override;
	bool visit(frontend::FunctionDefinition const&) override;
	void endVisit(frontend::Literal const&) override;
	void endVisit(frontend::Identifier const&) override;
	void endVisit(frontend::IdentifierPath const&) override;
	bool visit(frontend::MemberAccess const&) override;
	bool visit(frontend::ParameterList const&) override;
	void endVisit(frontend::PragmaDirective const&) override;
	bool visit(frontend::UserDefinedTypeName const&) override;
	bool visit(frontend::VariableDeclaration const&) override;

private:
	Json::Value m_encodedTokens;
	langutil::CharStream const* m_charStream;
	int m_lastLine;
	int m_lastStartChar;
};

} // end namespace

namespace fmt
{
    template <>
    struct formatter<solidity::lsp::SemanticTokenType>
	{
		using SemanticTokenType = solidity::lsp::SemanticTokenType;
        template <typename ParseContext>
        constexpr auto parse(ParseContext& ctx) { return ctx.begin(); }
        template <typename FormatContext>
        auto format(SemanticTokenType _value, FormatContext& _context)
		{
			switch (_value)
			{
				case SemanticTokenType::Class: return format_to(_context.out(), "Class");
				case SemanticTokenType::Comment: return format_to(_context.out(), "Comment");
				case SemanticTokenType::Enum: return format_to(_context.out(), "Enum");
				case SemanticTokenType::EnumMember: return format_to(_context.out(), "EnumMember");
				case SemanticTokenType::Event: return format_to(_context.out(), "Event");
				case SemanticTokenType::Function: return format_to(_context.out(), "Function");
				case SemanticTokenType::Interface: return format_to(_context.out(), "Interface");
				case SemanticTokenType::Keyword: return format_to(_context.out(), "Keyword");
				case SemanticTokenType::Macro: return format_to(_context.out(), "Macro");
				case SemanticTokenType::Method: return format_to(_context.out(), "Method");
				case SemanticTokenType::Modifier: return format_to(_context.out(), "Modifier");
				case SemanticTokenType::Number: return format_to(_context.out(), "Number");
				case SemanticTokenType::Operator: return format_to(_context.out(), "Operator");
				case SemanticTokenType::Parameter: return format_to(_context.out(), "Parameter");
				case SemanticTokenType::Property: return format_to(_context.out(), "Property");
				case SemanticTokenType::String: return format_to(_context.out(), "String");
				case SemanticTokenType::Struct: return format_to(_context.out(), "Struct");
				case SemanticTokenType::Type: return format_to(_context.out(), "Type");
				case SemanticTokenType::TypeParameter: return format_to(_context.out(), "TypeParameter");
				case SemanticTokenType::Variable: return format_to(_context.out(), "Variable");
			}
			return format_to(_context.out(), "({})", _value);
		}
    };
}
