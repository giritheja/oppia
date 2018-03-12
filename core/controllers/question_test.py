# Copyright 2017 The Oppia Authors. All Rights Reserved.
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

"""Tests for the Question controller."""

import json

from core.domain import collection_domain
from core.domain import collection_services
from core.domain import exp_domain
from core.domain import question_domain
from core.domain import question_services
from core.platform import models
from core.tests import test_utils
import feconf

(question_models,) = models.Registry.import_models([models.NAMES.question])


class QuestionsBatchHandlerTest(test_utils.GenericTestBase):
    """Test the handler for rendering questions batch."""

    def setUp(self):
        super(QuestionsBatchHandlerTest, self).setUp()

        self.collection_id = 'coll_0'
        self.exp_id = 'exp_1'
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        self.viewer_id = self.get_user_id_from_email(self.VIEWER_EMAIL)

        # Create a new collection and exploration.
        self.save_new_valid_collection(
            self.collection_id, self.owner_id, exploration_id=self.exp_id)

        # Add a skill.
        collection_services.update_collection(
            self.owner_id, self.collection_id, [{
                'cmd': collection_domain.CMD_ADD_COLLECTION_SKILL,
                'name': 'test'
            }], 'Add a new skill')
        collection = collection_services.get_collection_by_id(
            self.collection_id)
        self.skill_id = collection.get_skill_id_from_skill_name('test')
        collection_node = collection.get_node(self.exp_id)
        collection_node.update_acquired_skill_ids([self.skill_id])

        # Update the acquired skill IDs for the exploration.
        collection_services.update_collection(
            self.owner_id, self.collection_id, [{
                'cmd': collection_domain.CMD_EDIT_COLLECTION_NODE_PROPERTY,
                'property_name': (
                    collection_domain.COLLECTION_NODE_PROPERTY_ACQUIRED_SKILL_IDS), # pylint: disable=line-too-long
                'exploration_id': self.exp_id,
                'new_value': [self.skill_id]
            }], 'Update skill')

        question = question_domain.Question(
            'dummy', 'A Question',
            exp_domain.State.create_default_state('ABC').to_dict(), 1,
            self.collection_id, 'en')

        question_id = question_services.add_question(self.owner_id, question)
        self.question = question_services.get_question_by_id(question_id)
        question_services.add_question_id_to_skill(
            self.question.question_id, self.question.collection_id,
            self.skill_id, self.owner_id)

        self.signup(self.NEW_USER_EMAIL, self.NEW_USER_USERNAME)
        self.new_user_id = self.get_user_id_from_email(self.NEW_USER_EMAIL)
        collection_services.record_played_exploration_in_collection_context(
            self.new_user_id, self.collection_id, self.exp_id)
        self.payload = {}

    def test_get(self):
        """Test to verify the get method."""
        self.payload['collection_id'] = self.collection_id
        self.payload['stringified_skill_ids'] = json.dumps(
            [self.skill_id, 'test'])

        self.login(self.NEW_USER_EMAIL)
        response_json = self.get_json(
            '%s/batch' % feconf.QUESTION_DATA_URL, self.payload,
            expect_errors=False)
        self.assertIn(self.question.to_dict(), response_json['questions_dict'])
        self.assertEqual(len(response_json['questions_dict']), 1)
        self.logout()

        response_json = self.get_json(
            '%s/batch' % feconf.QUESTION_DATA_URL, self.payload,
            expect_errors=False)
        self.assertEqual(len(response_json['questions_dict']), 0)

        response = self.testapp.get(
            '%s/batch' % feconf.QUESTION_DATA_URL,
            expect_errors=True)
        self.assertEqual(response.status_int, 404)

        del self.payload['stringified_skill_ids']
        response = self.testapp.get(
            '%s/batch' % feconf.QUESTION_DATA_URL, self.payload,
            expect_errors=True)
        self.assertEqual(response.status_int, 404)


class QuestionsHandlerTest(test_utils.GenericTestBase):
    """Test the question handler."""

    def setUp(self):
        super(QuestionsHandlerTest, self).setUp()

        self.collection_id = 'coll_0'
        self.exp_id = 'exp_1'
        self.signup(self.NEW_USER_EMAIL, self.NEW_USER_USERNAME)
        self.new_user_id = self.get_user_id_from_email(self.NEW_USER_EMAIL)

        # Create a new collection and exploration.
        self.save_new_valid_collection(
            self.collection_id, self.new_user_id, exploration_id=self.exp_id)

        # Add a skill.
        collection_services.update_collection(
            self.new_user_id, self.collection_id, [{
                'cmd': collection_domain.CMD_ADD_COLLECTION_SKILL,
                'name': 'test'
            }], 'Add a new skill')
        collection = collection_services.get_collection_by_id(
            self.collection_id)
        self.skill_id = collection.get_skill_id_from_skill_name('test')
        collection_node = collection.get_node(self.exp_id)
        collection_node.update_acquired_skill_ids([self.skill_id])

        # Update the acquired skill IDs for the exploration.
        collection_services.update_collection(
            self.new_user_id, self.collection_id, [{
                'cmd': collection_domain.CMD_EDIT_COLLECTION_NODE_PROPERTY,
                'property_name': (
                    collection_domain.COLLECTION_NODE_PROPERTY_ACQUIRED_SKILL_IDS), # pylint: disable=line-too-long
                'exploration_id': self.exp_id,
                'new_value': [self.skill_id]
            }], 'Update skill')

        self.payload = {}

    def test_put(self):
        question = question_domain.Question(
            'dummy', 'A Question',
            exp_domain.State.create_default_state('ABC').to_dict(), 1,
            self.collection_id, 'en')

        question_id = question_services.add_question(
            self.new_user_id, question)
        question_services.add_question_id_to_skill(
            question_id, self.collection_id,
            self.skill_id, self.new_user_id)

        collection_services.record_played_exploration_in_collection_context(
            self.new_user_id, self.collection_id, self.exp_id)
        change_list = [{'cmd': 'update_question_property',
                        'property_name': 'title',
                        'new_value': 'ABC',
                        'old_value': 'A Question'}]
        self.payload['change_list'] = json.dumps(change_list)
        self.payload['commit_message'] = 'update title'
        self.login(self.NEW_USER_EMAIL)
        response_json = self.put_json(
            '%s/%s/%s' % (
                feconf.QUESTION_DATA_URL, self.collection_id, question_id),
            self.payload, expect_errors=False)
        self.assertIn('question_id', response_json.keys())

        del self.payload['change_list']
        self.put_json(
            '%s/%s/%s' % (feconf.QUESTION_DATA_URL, self.collection_id,
                question_id), self.payload, expect_errors=True,
            expected_status_int=404)

        del self.payload['commit_message']
        self.payload['change_list'] = json.dumps(change_list)
        self.put_json(
            '%s/%s/%s' % (feconf.QUESTION_DATA_URL, self.collection_id,
                question_id), self.payload, expect_errors=True,
            expected_status_int=404)

        self.payload['commit_message'] = 'update title'
        self.put_json(
            '%s/%s' % (feconf.QUESTION_DATA_URL, self.collection_id),
            self.payload, expect_errors=True,
            expected_status_int=404)

    def test_delete(self):
        question = question_domain.Question(
            'dummy', 'A Question',
            exp_domain.State.create_default_state('ABC').to_dict(), 1,
            self.collection_id, 'en')

        question_id = question_services.add_question(
            self.new_user_id, question)
        question_services.add_question_id_to_skill(
            question_id, self.collection_id, self.skill_id,
            self.new_user_id)
        self.login(self.NEW_USER_EMAIL)
        response = self.testapp.delete(
            '%s/%s/%s' % (
                feconf.QUESTION_DATA_URL, self.collection_id, question_id),
            expect_errors=False)
        self.assertEqual(response.status_int, 200)

        response = self.testapp.delete(
            '%s/%s' % (
                feconf.QUESTION_DATA_URL, self.collection_id),
            expect_errors=True)
        self.assertEqual(response.status_int, 404)

        response = self.testapp.delete(
            '%s/' % feconf.QUESTION_DATA_URL, expect_errors=True)
        self.assertEqual(response.status_int, 404)


class QuestionsPostHandlerTest(test_utils.GenericTestBase):
    """Test the question handler."""

    def setUp(self):
        super(QuestionsPostHandlerTest, self).setUp()

        self.collection_id = 'coll_0'
        self.exp_id = 'exp_1'
        self.signup(self.NEW_USER_EMAIL, self.NEW_USER_USERNAME)
        self.new_user_id = self.get_user_id_from_email(self.NEW_USER_EMAIL)

        # Create a new collection and exploration.
        self.save_new_valid_collection(
            self.collection_id, self.new_user_id, exploration_id=self.exp_id)

        # Add a skill.
        collection_services.update_collection(
            self.new_user_id, self.collection_id, [{
                'cmd': collection_domain.CMD_ADD_COLLECTION_SKILL,
                'name': 'test'
            }], 'Add a new skill')
        collection = collection_services.get_collection_by_id(
            self.collection_id)
        self.skill_id = collection.get_skill_id_from_skill_name('test')
        collection_node = collection.get_node(self.exp_id)
        collection_node.update_acquired_skill_ids([self.skill_id])

        # Update the acquired skill IDs for the exploration.
        collection_services.update_collection(
            self.new_user_id, self.collection_id, [{
                'cmd': collection_domain.CMD_EDIT_COLLECTION_NODE_PROPERTY,
                'property_name': (
                    collection_domain.COLLECTION_NODE_PROPERTY_ACQUIRED_SKILL_IDS), # pylint: disable=line-too-long
                'exploration_id': self.exp_id,
                'new_value': [self.skill_id]
            }], 'Update skill')

        self.payload = {}

    def test_post(self):
        """Test to verify Post method."""
        question = question_domain.Question(
            'dummy', 'A Question',
            exp_domain.State.create_default_state('ABC').to_dict(), 1,
            self.collection_id, 'en')
        self.payload['question'] = question.to_dict()
        self.payload['skill_id'] = self.skill_id
        self.login(self.NEW_USER_EMAIL)
        response_json = self.post_json(
            '%s' % feconf.QUESTION_POST_URL, self.payload,
            expect_errors=False)
        self.assertIn('question_id', response_json.keys())

        del self.payload['skill_id']
        response = self.post_json(
            '%s' % feconf.QUESTION_POST_URL, {'payload': (
                json.dumps(self.payload))}, expect_errors=True,
            expected_status_int=404)

        del self.payload['question']
        response = self.post_json(
            '%s' % feconf.QUESTION_POST_URL, {'payload': (
                json.dumps(self.payload))}, expect_errors=True,
            expected_status_int=404)


class QuestionManagerHandlerTest(test_utils.GenericTestBase):
    """Test the question handler."""

    def setUp(self):
        super(QuestionManagerHandlerTest, self).setUp()

        self.collection_id = 'coll_0'
        self.exp_id = 'exp_1'
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        self.viewer_id = self.get_user_id_from_email(self.VIEWER_EMAIL)

        # Create a new collection and exploration.
        self.save_new_valid_collection(
            self.collection_id, self.owner_id, exploration_id=self.exp_id)

        # Add a skill.
        collection_services.update_collection(
            self.owner_id, self.collection_id, [{
                'cmd': collection_domain.CMD_ADD_COLLECTION_SKILL,
                'name': 'test'
            }], 'Add a new skill')
        collection = collection_services.get_collection_by_id(
            self.collection_id)
        self.skill_id = collection.get_skill_id_from_skill_name('test')
        collection_node = collection.get_node(self.exp_id)
        collection_node.update_acquired_skill_ids([self.skill_id])

        # Update the acquired skill IDs for the exploration.
        collection_services.update_collection(
            self.owner_id, self.collection_id, [{
                'cmd': collection_domain.CMD_EDIT_COLLECTION_NODE_PROPERTY,
                'property_name': (
                    collection_domain.COLLECTION_NODE_PROPERTY_ACQUIRED_SKILL_IDS), # pylint: disable=line-too-long
                'exploration_id': self.exp_id,
                'new_value': [self.skill_id]
            }], 'Update skill')

        question = question_domain.Question(
            'dummy', 'A Question',
            exp_domain.State.create_default_state('ABC').to_dict(), 1,
            self.collection_id, 'en')

        question_id = question_services.add_question(self.owner_id, question)
        self.question = question_services.get_question_by_id(question_id)
        question_services.add_question_id_to_skill(
            self.question.question_id, self.question.collection_id,
            self.skill_id, self.owner_id)

        self.payload = {}

    def test_get(self):
        """Test to verify get method."""
        self.payload['collection_id'] = self.collection_id
        response_json = self.get_json(
            '%s' % feconf.QUESTION_MANAGER_URL, self.payload,
            expect_errors=False)
        expected_question_summary = question_domain.QuestionSummary(
            self.question.question_id, self.question.title, ['test'])
        self.assertIn(
            expected_question_summary.to_dict(),
            response_json['question_summary_dicts'])

        response = self.testapp.get(
            '%s/batch' % feconf.QUESTION_MANAGER_URL,
            expect_errors=True)
        self.assertEqual(response.status_int, 404)

        del self.payload['collection_id']
        response = self.testapp.get(
            '%s/batch' % feconf.QUESTION_MANAGER_URL, self.payload,
            expect_errors=True)
        self.assertEqual(response.status_int, 404)


class QuestionIntegrationTest(test_utils.GenericTestBase):
    """Test the handlers for managing questions."""

    def setUp(self):
        super(QuestionIntegrationTest, self).setUp()

        self.collection_id = 'coll_0'
        self.exp_id = 'exp_1'
        self.signup(self.NEW_USER_EMAIL, self.NEW_USER_USERNAME)
        self.new_user_id = self.get_user_id_from_email(self.NEW_USER_EMAIL)

        # Create a new collection and exploration.
        self.save_new_valid_collection(
            self.collection_id, self.new_user_id, exploration_id=self.exp_id)

        # Add a skill.
        collection_services.update_collection(
            self.new_user_id, self.collection_id, [{
                'cmd': collection_domain.CMD_ADD_COLLECTION_SKILL,
                'name': 'test'
            }], 'Add a new skill')
        collection = collection_services.get_collection_by_id(
            self.collection_id)
        self.skill_id = collection.get_skill_id_from_skill_name('test')
        collection_node = collection.get_node(self.exp_id)
        collection_node.update_acquired_skill_ids([self.skill_id])

        # Update the acquired skill IDs for the exploration.
        collection_services.update_collection(
            self.new_user_id, self.collection_id, [{
                'cmd': collection_domain.CMD_EDIT_COLLECTION_NODE_PROPERTY,
                'property_name': (
                    collection_domain.COLLECTION_NODE_PROPERTY_ACQUIRED_SKILL_IDS), # pylint: disable=line-too-long
                'exploration_id': self.exp_id,
                'new_value': [self.skill_id]
            }], 'Update skill')

        self.payload = {}


    def test_black_box(self):
        question = question_domain.Question(
                'dummy', 'A Question',
                exp_domain.State.create_default_state('ABC').to_dict(), 1,
                self.collection_id, 'en')
        self.payload['question'] = question.to_dict()
        self.payload['skill_id'] = self.skill_id
        self.login(self.NEW_USER_EMAIL)
        response_json = self.post_json(
            '%s' % feconf.QUESTION_POST_URL, self.payload,
            expect_errors=False)
        self.assertIn('question_id', response_json.keys())
        question_id = response_json['question_id']

        another_question = question_domain.Question(
            'dummy', 'Question 2',
            exp_domain.State.create_default_state('ABC').to_dict(), 1,
            self.collection_id, 'en')
        self.payload['question'] = question.to_dict()
        self.payload['skill_id'] = self.skill_id
        self.login(self.NEW_USER_EMAIL)
        response_json = self.post_json(
            '%s' % feconf.QUESTION_POST_URL, self.payload,
            expect_errors=False)
        self.assertIn('question_id', response_json.keys())
        another_question_id = response_json['question_id']

        del self.payload['question']
        del self.payload['skill_id']
        self.payload['collection_id'] = self.collection_id
        response_json = self.get_json(
            '%s' % feconf.QUESTION_MANAGER_URL, self.payload,
            expect_errors=False)
        self.assertIn('question_summary_dicts', response_json.keys())
        question_summary_dicts = response_json['question_summary_dicts']
        self.assertEqual(len(question_summary_dicts), 2)
        response = self.testapp.delete(
            '%s/%s/%s' % (
                feconf.QUESTION_DATA_URL, self.collection_id,
                str(another_question_id)),
            expect_errors=False)
        self.assertEqual(response.status_int, 200)
        response_json = self.get_json(
            '%s' % feconf.QUESTION_MANAGER_URL, self.payload,
            expect_errors=False)
        self.assertIn('question_summary_dicts', response_json.keys())
        question_summary_dicts = response_json['question_summary_dicts']
        self.assertEqual(len(question_summary_dicts), 1)
        self.assertIn(question_id, question_summary_dicts[0]['question_id'])
