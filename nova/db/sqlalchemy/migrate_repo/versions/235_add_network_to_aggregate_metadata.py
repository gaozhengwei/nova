# Copyright 2015 Lecloud Corporation
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

from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import Text


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    # Add a new column network to network info for aggregate metadata
    aggregate_metadata = Table('aggregate_metadata', meta, autoload=True)
    shadow_aggregate_metadata = Table('shadow_aggregate_metadata',
                                      meta, autoload=True)

    network = Column('network', Text, default='[]')
    shadow_network = Column('network', Text, default='[]')
    aggregate_metadata.create_column(network)
    shadow_aggregate_metadata.create_column(shadow_network)


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    # Remove the new column
    aggregate_metadata = Table('aggregate_metadata', meta, autoload=True)
    shadow_aggregate_metadata = Table('shadow_aggregate_metadata',
                                       meta, autoload=True)

    aggregate_metadata.drop_column('network')
    shadow_aggregate_metadata.drop_column('network')
