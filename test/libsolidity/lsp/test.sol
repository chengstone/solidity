// SPDX-License-Identifier: UNLICENSED
pragma solidity >=0.8.0;

/// Some Error type E.
error E(uint, uint);

enum Wheather {
    Sunny,
    Cloudy,
    Rainy
}

/// My contract MyContract.
///
contract MyContract
{
    Wheather lastWheather = Wheather.Rainy;

    constructor()
    {
    }

    /// Sum is summing two args and returning the result
    ///
    /// @param a me it is
    /// @param b me it is also
    function sum(uint a, uint b) public pure returns (uint)
    {
        Wheather weather = Wheather.Sunny;
        uint foo = 12345;
        if (a == b)
            revert E(a, b);
        weather = Wheather.Cloudy;
        return a + b + foo;
    }

    function main() public pure returns (uint)
    {
        return sum(2, 3 - 123 + 456);
    }
}

contract D
{
    function main() public payable returns (uint)
    {
        MyContract c = new MyContract();
        return c.sum(2, 3);
    }
}
