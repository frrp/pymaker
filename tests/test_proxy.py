# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2018 bargst
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import pytest
from web3 import Web3

from pymaker import Address, Calldata
from pymaker.proxy import DSProxyCache, DSProxy, DSProxyFactory, LogCreated


@pytest.fixture(scope="session")
def web3():
    web3 = Web3(Web3.HTTPProvider("http://localhost:8555"))
    web3.eth.defaultAccount = web3.eth.accounts[0]
    return web3


@pytest.fixture(scope="session")
def our_address(web3):
    return Address(web3.eth.accounts[0])


@pytest.fixture(scope="session")
def other_address(web3):
    return Address(web3.eth.accounts[1])


@pytest.fixture(scope="session")
def proxy_cache(web3):
    return DSProxyCache.deploy(web3=web3)


@pytest.fixture(scope="session")
def proxy_factory(web3):
    return DSProxyFactory.deploy(web3=web3)


@pytest.fixture(scope="session")
def proxy(web3, proxy_cache):
    return DSProxy.deploy(web3=web3, cache=proxy_cache.address)


class TestProxyCache:
    """ `DSProxyCache` class testing"""

    def test_read(self, proxy_cache: DSProxyCache):
        assert proxy_cache.read('0x001122') == Address('0x0000000000000000000000000000000000000000')

    def test_write_invalid(self, proxy_cache: DSProxyCache):
        # when
        address = proxy_cache.write('0x001122').transact()

        # then
        assert address is None
        assert proxy_cache.read('0x001122') == Address('0x0000000000000000000000000000000000000000')

    def test_write(self, proxy_cache: DSProxyCache):
        # when
        proxy_cache.write('0x' + DSProxyCache.bin).transact()

        # then
        assert proxy_cache.read('0x' + DSProxyCache.bin) != Address('0x0000000000000000000000000000000000000000')


class TestProxyFactory:
    """ `DSProxyFactory` class testing"""

    def test_build(self, proxy_factory: DSProxyFactory):
        assert proxy_factory.build().transact()

    def test_past_build(self, proxy_factory: DSProxyFactory, our_address):
        # given
        past_build = proxy_factory.past_build(proxy_factory.web3.eth.blockNumber)
        past_build_count = len(past_build)

        # when
        assert proxy_factory.build().transact()

        # then
        past_build = proxy_factory.past_build(1)
        assert past_build
        assert len(past_build) == past_build_count + 1

        past_build: LogCreated = past_build[0]
        assert past_build.owner == our_address
        assert past_build.sender == our_address
        assert past_build.cache == proxy_factory.cache()
        assert proxy_factory.is_proxy(past_build.proxy)

    def test_build_for(self, proxy_factory: DSProxyFactory, other_address):
        # given
        assert proxy_factory.is_proxy(other_address) is False

        # when
        receipt = proxy_factory.build_for(other_address).transact()
        assert receipt

        build_event = proxy_factory.log_created(receipt)[0]

        # then
        assert build_event.owner == other_address
        assert proxy_factory.is_proxy(build_event.proxy)

    def test_cache(self, proxy_factory: DSProxyFactory, other_address):
        assert proxy_factory.cache() is not Address('0x0000000000000000000000000000000000000000')


class TestProxy:
    """ `DSProxy` class testing"""

    def test_execute(self, proxy: DSProxy):
        assert proxy.execute('0x' + DSProxyFactory.bin, Calldata.from_signature("build()", [])).transact()

    def test_execute_at(self, proxy: DSProxy):
        # given
        proxy_cache = DSProxyCache(proxy.web3, proxy.cache())
        proxy_cache.write('0x' + DSProxyFactory.bin).transact()
        new_factory_addr = proxy_cache.read('0x' + DSProxyFactory.bin)
        assert new_factory_addr

        # when
        receipt = proxy.execute_at(new_factory_addr, Calldata.from_signature("build(address)",
                                                                             [proxy.address.address])).transact()
        assert receipt
        build_event = DSProxyFactory.log_created(receipt)[0]

        # then
        assert build_event.owner == proxy.address
