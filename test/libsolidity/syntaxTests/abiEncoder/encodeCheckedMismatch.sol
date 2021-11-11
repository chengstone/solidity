
contract C {
    function f(int a) public {}
    function f2(int a, string memory b) public {}

	function fail() public returns(bytes memory) {
		return abi.encodeChecked(f, ("test"));
	}
	function fail2() public returns(bytes memory) {
		return abi.encodeChecked(f, (1, 2));
	}
	function fail3() public returns(bytes memory) {
		return abi.encodeChecked(f, ());
	}
	function fail4() public returns(bytes memory) {
		return abi.encodeChecked(f);
	}
	function fail5() public returns(bytes memory) {
		return abi.encodeChecked(1, f);
	}
	function success() public returns(bytes memory) {
		return abi.encodeChecked(f, (1));
	}
	function success2() public returns(bytes memory) {
		return abi.encodeChecked(f, 1);
	}
	function success3() public returns(bytes memory) {
		return abi.encodeChecked(f2, (1, "test"));
	}
}
// ----
// TypeError 5407: (154-184): Parameter mismatch: Expected "int256" instead of "literal_string "test"" for the tuple component at position 0.
// TypeError 7788: (247-275): Expected 1 instead of 2 components for the tuple parameter.
// TypeError 7788: (338-362): Expected 1 instead of 0 components for the tuple parameter.
// TypeError 6219: (425-445): Expected two arguments: a function pointer followed by a tuple.
// TypeError 5511: (508-531): Expected first argument to be a function pointer, not "int_const 1".
