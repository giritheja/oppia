# coding: utf-8
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Commands for moderator message operations."""

from core.platform import models
import feconf

taskqueue_services = models.Registry.import_taskqueue_services()


def enqueue_flag_exploration_email_task(exploration_id, report_text,
                                        reporter_id):
    """Adds a 'send flagged exploration email' task into taskqueue."""
    if reporter_id is None:
        raise Exception('User has to be logged in to report.')
    else:
        payload = {
            'exploration_id': exploration_id,
            'report_text': report_text,
            'reporter_id': reporter_id,
            }

        # Email about flagged explorations are sent immediately to moderators.
        taskqueue_services.enqueue_task(
            feconf.FLAG_EXPLORATION_EMAIL_HANDLER_URL, payload, 0)
