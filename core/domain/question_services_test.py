# coding: utf-8
#
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

from core.domain import exp_domain
from core.domain import collection_domain
from core.domain import collection_services
from core.domain import question_domain
from core.domain import question_services
from core.domain import user_services
from core.platform import models
from core.tests import test_utils

(question_models,) = models.Registry.import_models([models.NAMES.question])
memcache_services = models.Registry.import_memcache_services()


class QuestionServicesUnitTest(test_utils.GenericTestBase):
    """Test the question services module."""

    def setUp(self):
        """Before each individual test, create dummy user."""
        super(QuestionServicesUnitTest, self).setUp()

        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)
        user_services.create_new_user(self.owner_id, self.OWNER_EMAIL)
        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)

    def test_get_question_by_id(self):
        state = exp_domain.State.create_default_state('ABC')
        question_data = state.to_dict()
        question_id = 'dummy'
        title = 'A Question'
        question_data_schema_version = 1
        collection_id = 'col1'
        language_code = 'en'
        question = question_domain.Question(
            question_id, title, question_data, question_data_schema_version,
            collection_id, language_code)
        question.validate()

        question_model = question_services.add_question(self.owner_id, question)
        question = question_services.get_question_by_id(question_model.id)

        self.assertEqual(question.title, title)

    def test_get_questions_by_ids(self):
        state = exp_domain.State.create_default_state('ABC')
        question_data = state.to_dict()
        question_id = 'dummy'
        title = 'A Question'
        question_data_schema_version = 1
        collection_id = 'col1'
        language_code = 'en'
        question = question_domain.Question(
            question_id, title, question_data, question_data_schema_version,
            collection_id, language_code)
        question.validate()

        question1_model = question_services.add_question(
            self.owner_id, question)
        state = exp_domain.State.create_default_state('ABC')
        question_data = state.to_dict()
        question_id = 'dummy2'
        title = 'A Question2'
        question_data_schema_version = 1
        collection_id = 'col2'
        language_code = 'en'
        question = question_domain.Question(
            question_id, title, question_data, question_data_schema_version,
            collection_id, language_code)
        question.validate()

        question2_model = question_services.add_question(
            self.owner_id, question)
        questions = question_services.get_questions_by_ids(
            [question1_model.id, question2_model.id])
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].title, question1_model.title)
        self.assertEqual(questions[1].title, question2_model.title)

    def test_add_question(self):
        state = exp_domain.State.create_default_state('ABC')
        question_data = state.to_dict()
        question_id = 'dummy'
        title = 'A Question'
        question_data_schema_version = 1
        collection_id = 'col1'
        language_code = 'en'
        question = question_domain.Question(
            question_id, title, question_data, question_data_schema_version,
            collection_id, language_code)
        question.validate()

        question_model = question_services.add_question(self.owner_id, question)
        model = question_models.QuestionModel.get(question_model.id)

        self.assertEqual(model.title, title)
        self.assertEqual(model.question_data, question_data)
        self.assertEqual(model.question_data_schema_version,
                         question_data_schema_version)
        self.assertEqual(model.collection_id, collection_id)
        self.assertEqual(model.language_code, language_code)

    def test_delete_question(self):
        state = exp_domain.State.create_default_state('ABC')
        question_data = state.to_dict()
        question_id = 'dummy'
        title = 'A Question'
        question_data_schema_version = 1
        collection_id = 'col1'
        language_code = 'en'
        question = question_domain.Question(
            question_id, title, question_data, question_data_schema_version,
            collection_id, language_code)
        question.validate()

        question_model = question_services.add_question(self.owner_id, question)
        question_services.delete_question(self.owner_id, question_model.id)

        with self.assertRaisesRegexp(Exception, (
            'Entity for class QuestionModel with id %s not found' %(
                question_model.id))):
            question_models.QuestionModel.get(question_model.id)

    def test_update_question(self):
        state = exp_domain.State.create_default_state('ABC')
        question_data = state.to_dict()
        question_id = 'dummy'
        title = 'A Question'
        question_data_schema_version = 1
        collection_id = 'col1'
        language_code = 'en'
        question = question_domain.Question(
            question_id, title, question_data, question_data_schema_version,
            collection_id, language_code)
        question.validate()

        question_model = question_services.add_question(self.owner_id, question)
        change_dict = {'cmd': 'update_question_property',
                       'property_name': 'title',
                       'new_value': 'ABC',
                       'old_value': 'A Question'}
        change_list = [question_domain.QuestionChange(change_dict)]
        question_services.update_question(
            self.owner_id, question_model.id, change_list, 'updated title')

        model = question_models.QuestionModel.get(question_model.id)
        self.assertEqual(model.title, 'ABC')
        self.assertEqual(model.question_data, question_data)
        self.assertEqual(model.question_data_schema_version,
                         question_data_schema_version)
        self.assertEqual(model.collection_id, collection_id)
        self.assertEqual(model.language_code, language_code)

    def test_get_question_batch(self):
        coll_id_0 = '0_collection_id'
        exp_id_0 = '0_exploration_id'
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)

        # Create a new collection and exploration.
        self.save_new_valid_collection(
            coll_id_0, self.owner_id, exploration_id=exp_id_0)

        # Add a skill.
        collection_services.update_collection(
            self.owner_id, coll_id_0, [{
                'cmd': collection_domain.CMD_ADD_COLLECTION_SKILL,
                'name': 'test'
            }], 'Add a new skill')
        collection = collection_services.get_collection_by_id(
            coll_id_0)
        skill_id = collection.get_skill_id_from_skill_name('test')
        collection_node = collection.get_node(exp_id_0)
        collection_node.update_acquired_skill_ids([skill_id])
        # Update a skill.
        collection_services.update_collection(
            self.owner_id, coll_id_0, [{
                'cmd': collection_domain.CMD_EDIT_COLLECTION_NODE_PROPERTY,
                'property_name': (
                    collection_domain.COLLECTION_NODE_PROPERTY_ACQUIRED_SKILL_IDS), # pylint: disable=line-too-long
                'exploration_id': exp_id_0,
                'new_value': [skill_id]
            }], 'Update skill')

        state = exp_domain.State.create_default_state('ABC')
        question_data = state.to_dict()
        question_id = 'dummy'
        title = 'A Question'
        question_data_schema_version = 1
        collection_id = coll_id_0
        language_code = 'en'
        question = question_domain.Question(
            question_id, title, question_data, question_data_schema_version,
            collection_id, language_code)
        question.validate()

        question_model = question_services.add_question(self.owner_id, question)
        question = question_services.get_question_by_id(question_model.id)
        question.add_skill('test', self.owner_id)
        collection_services.record_played_exploration_in_collection_context(
            self.owner_id, coll_id_0, exp_id_0)
        question_batch = question_services.get_questions_batch(
            coll_id_0, [skill_id], self.owner_id, 1)
        self.assertEqual(question_batch[0].title, question.title)
