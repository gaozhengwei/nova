# Copyright (c) 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Tests for resource tracker claims."""

import re
import uuid

import mock
import six

from nova.compute import claims
from nova import exception
from nova.objects import instance_pci_requests as ins_pci_req_obj
from nova.pci import pci_manager
from nova import test
from nova.tests.pci import pci_fakes


class FakeResourceHandler(object):
    test_called = False
    usage_is_instance = False

    def test_resources(self, usage, limits):
        self.test_called = True
        self.usage_is_itype = usage.get('name') is 'fakeitype'
        return []


class DummyTracker(object):
    icalled = False
    rcalled = False
    ext_resources_handler = FakeResourceHandler()
    pci_tracker = pci_manager.PciDevTracker()

    def abort_instance_claim(self, *args, **kwargs):
        self.icalled = True

    def drop_resize_claim(self, *args, **kwargs):
        self.rcalled = True

    def new_pci_tracker(self):
        self.pci_tracker = pci_manager.PciDevTracker()


class ClaimTestCase(test.NoDBTestCase):

    def setUp(self):
        super(ClaimTestCase, self).setUp()
        self.resources = self._fake_resources()
        self.tracker = DummyTracker()

    def _claim(self, limits=None, overhead=None, **kwargs):
        instance = self._fake_instance(**kwargs)
        if overhead is None:
            overhead = {'memory_mb': 0}
        return claims.Claim('context', instance, self.tracker, self.resources,
                            overhead=overhead, limits=limits)

    def _fake_instance(self, **kwargs):
        instance = {
            'uuid': str(uuid.uuid1()),
            'memory_mb': 1024,
            'root_gb': 10,
            'ephemeral_gb': 5,
            'vcpus': 1,
            'system_metadata': {}
        }
        instance.update(**kwargs)
        return instance

    def _fake_instance_type(self, **kwargs):
        instance_type = {
            'id': 1,
            'name': 'fakeitype',
            'memory_mb': 1,
            'vcpus': 1,
            'root_gb': 1,
            'ephemeral_gb': 2
        }
        instance_type.update(**kwargs)
        return instance_type

    def _fake_resources(self, values=None):
        resources = {
            'memory_mb': 2048,
            'memory_mb_used': 0,
            'free_ram_mb': 2048,
            'local_gb': 20,
            'local_gb_used': 0,
            'free_disk_gb': 20,
            'vcpus': 2,
            'vcpus_used': 0
        }
        if values:
            resources.update(values)
        return resources

    # TODO(lxsli): Remove once Py2.6 is deprecated
    def assertRaisesRegexp(self, re_obj, e, fn, *a, **kw):
        try:
            fn(*a, **kw)
            self.fail("Expected exception not raised")
        except e as ee:
            self.assertTrue(re.search(re_obj, str(ee)))

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_memory_unlimited(self, mock_get):
        self._claim(memory_mb=99999999)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_disk_unlimited_root(self, mock_get):
        self._claim(root_gb=999999)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_disk_unlimited_ephemeral(self, mock_get):
        self._claim(ephemeral_gb=999999)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_memory_with_overhead(self, mock_get):
        overhead = {'memory_mb': 8}
        limits = {'memory_mb': 2048}
        claim = self._claim(memory_mb=2040, limits=limits,
                            overhead=overhead)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_memory_with_overhead_insufficient(self, mock_get):
        overhead = {'memory_mb': 9}
        limits = {'memory_mb': 2048}

        self.assertRaises(exception.ComputeResourcesUnavailable,
                          self._claim, limits=limits, overhead=overhead,
                          memory_mb=2040)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_memory_oversubscription(self, mock_get):
        self._claim(memory_mb=4096)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_memory_insufficient(self, mock_get):
        limits = {'memory_mb': 8192}
        self.assertRaises(exception.ComputeResourcesUnavailable,
                          self._claim, limits=limits, memory_mb=16384)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_disk_oversubscription(self, mock_get):
        limits = {'disk_gb': 60}
        claim = self._claim(root_gb=10, ephemeral_gb=40,
                            limits=limits)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_disk_insufficient(self, mock_get):
        limits = {'disk_gb': 45}
        self.assertRaisesRegexp(re.compile("disk", re.IGNORECASE),
                exception.ComputeResourcesUnavailable,
                self._claim, limits=limits, root_gb=10, ephemeral_gb=40)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_disk_and_memory_insufficient(self, mock_get):
        limits = {'disk_gb': 45, 'memory_mb': 8192}
        self.assertRaisesRegexp(re.compile("memory.*disk", re.IGNORECASE),
                exception.ComputeResourcesUnavailable,
                self._claim, limits=limits, root_gb=10, ephemeral_gb=40,
                memory_mb=16384)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_disk_and_cpu_and_memory_insufficient(self, mock_get):
        limits = {'disk_gb': 45, 'vcpu': 16, 'memory_mb': 8192}
        pat = "memory.*disk.*vcpus"
        self.assertRaisesRegexp(re.compile(pat, re.IGNORECASE),
                exception.ComputeResourcesUnavailable,
                self._claim, limits=limits, root_gb=10, ephemeral_gb=40,
                vcpus=17, memory_mb=16384)

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    @pci_fakes.patch_pci_whitelist
    def test_pci_pass(self, mock_get):
        dev_dict = {
            'compute_node_id': 1,
            'address': 'a',
            'product_id': 'p',
            'vendor_id': 'v',
            'status': 'available'}
        self.tracker.new_pci_tracker()
        self.tracker.pci_tracker.set_hvdevs([dev_dict])
        claim = self._claim()
        request = ins_pci_req_obj.InstancePCIRequest(count=1,
            spec=[{'vendor_id': 'v', 'product_id': 'p'}])
        mock_get.return_value = ins_pci_req_obj.InstancePCIRequests(
            requests=[request])
        self.assertIsNone(claim._test_pci())

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    @pci_fakes.patch_pci_whitelist
    def test_pci_fail(self, mock_get):
        dev_dict = {
            'compute_node_id': 1,
            'address': 'a',
            'product_id': 'p',
            'vendor_id': 'v1',
            'status': 'available'}
        self.tracker.new_pci_tracker()
        self.tracker.pci_tracker.set_hvdevs([dev_dict])
        claim = self._claim()
        request = ins_pci_req_obj.InstancePCIRequest(count=1,
            spec=[{'vendor_id': 'v', 'product_id': 'p'}])
        mock_get.return_value = ins_pci_req_obj.InstancePCIRequests(
            requests=[request])
        claim._test_pci()

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    @pci_fakes.patch_pci_whitelist
    def test_pci_pass_no_requests(self, mock_get):
        dev_dict = {
            'compute_node_id': 1,
            'address': 'a',
            'product_id': 'p',
            'vendor_id': 'v',
            'status': 'available'}
        self.tracker.new_pci_tracker()
        self.tracker.pci_tracker.set_hvdevs([dev_dict])
        claim = self._claim()
        claim._test_pci()

    '''
    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_ext_resources(self, mock_get):
        self._claim()
        self.assertTrue(self.tracker.ext_resources_handler.test_called)
        self.assertFalse(self.tracker.ext_resources_handler.usage_is_itype)'''

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_abort(self, mock_get):
        claim = self._abort()
        self.assertTrue(claim.tracker.icalled)

    def _abort(self):
        claim = None
        try:
            with self._claim(memory_mb=4096) as claim:
                raise test.TestingException("abort")
        except test.TestingException:
            pass

        return claim

class ResizeClaimTestCase(ClaimTestCase):

    def setUp(self):
        super(ResizeClaimTestCase, self).setUp()
        self.instance = self._fake_instance()

    def _claim(self, limits=None, overhead=None, **kwargs):
        instance_type = self._fake_instance_type(**kwargs)
        if overhead is None:
            overhead = {'memory_mb': 0}
        return claims.ResizeClaim('context', self.instance, instance_type,
                                  self.tracker, self.resources,
                                  overhead=overhead, limits=limits)

    '''
    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_ext_resources(self, mock_get):
        self._claim()
        self.assertTrue(self.tracker.ext_resources_handler.test_called)
        self.assertTrue(self.tracker.ext_resources_handler.usage_is_itype)'''

    @mock.patch('nova.objects.instance_pci_requests.InstancePCIRequests.get_by_instance_uuid',
                return_value=ins_pci_req_obj.InstancePCIRequests(requests=[]))
    def test_abort(self, mock_get):
        claim = self._abort()
        self.assertTrue(claim.tracker.rcalled)
