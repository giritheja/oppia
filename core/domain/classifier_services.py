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

"""Services for classifier data models."""

import datetime

import logging

from core.domain import classifier_domain
from core.domain import classifier_registry
from core.domain import exp_domain
from core.domain import interaction_registry
from core.platform import models

import feconf

(classifier_models, exp_models) = models.Registry.import_models(
    [models.NAMES.classifier, models.NAMES.exploration])


def classify(state, answer):
    """Classify the answer using the string classifier.

    This should only be called if the string classifier functionality is
    enabled, and the interaction is trainable.

    Normalize the answer and classifies the answer if the interaction has a
    classifier associated with it. Otherwise, classifies the answer to the
    default outcome.

    Returns a dict with the following keys:
        'outcome': A dict representing the outcome of the answer group matched.
        'answer_group_index': An index into the answer groups list indicating
            which one was selected as the group which this answer belongs to.
            This is equal to the number of answer groups if the default outcome
            was matched.
        'rule_spec_index': An index into the rule specs list of the matched
            answer group which was selected that indicates which rule spec was
            matched. This is equal to 0 if the default outcome is selected.
    When the default rule is matched, outcome is the default_outcome of the
    state's interaction.
    """
    assert feconf.ENABLE_ML_CLASSIFIERS

    interaction_instance = interaction_registry.Registry.get_interaction_by_id(
        state.interaction.id)
    normalized_answer = interaction_instance.normalize_answer(answer)
    response = None

    if interaction_instance.is_string_classifier_trainable:
        response = classify_string_classifier_rule(state, normalized_answer)
    else:
        raise Exception('No classifier found for interaction.')

    if response is not None:
        return response
    elif state.interaction.default_outcome is not None:
        return {
            'outcome': state.interaction.default_outcome.to_dict(),
            'answer_group_index': len(state.interaction.answer_groups),
            'classification_certainty': 0.0,
            'rule_spec_index': 0
        }

    raise Exception(
        'Something has seriously gone wrong with the exploration. Oppia does '
        'not know what to do with this answer. Please contact the '
        'exploration owner.')


def classify_string_classifier_rule(state, normalized_answer):
    """Run the classifier if no prediction has been made yet. Currently this
    is behind a development flag.
    """
    best_matched_answer_group = None
    best_matched_answer_group_index = len(state.interaction.answer_groups)
    best_matched_rule_spec_index = None

    sc = classifier_registry.Registry.get_classifier_by_algorithm_id(
        feconf.INTERACTION_CLASSIFIER_MAPPING[state.interaction.id][
            'algorithm_id'])

    training_examples = [
        [doc, []] for doc in state.interaction.confirmed_unclassified_answers]
    for (answer_group_index, answer_group) in enumerate(
            state.interaction.answer_groups):
        classifier_rule_spec_index = answer_group.get_classifier_rule_index()
        if classifier_rule_spec_index is not None:
            classifier_rule_spec = answer_group.rule_specs[
                classifier_rule_spec_index]
        else:
            classifier_rule_spec = None
        if classifier_rule_spec is not None:
            training_examples.extend([
                [doc, [str(answer_group_index)]]
                for doc in classifier_rule_spec.inputs['training_data']])
    if len(training_examples) > 0:
        sc.train(training_examples)
        labels = sc.predict([normalized_answer])
        predicted_label = labels[0]
        if predicted_label != feconf.DEFAULT_CLASSIFIER_LABEL:
            predicted_answer_group_index = int(predicted_label)
            predicted_answer_group = state.interaction.answer_groups[
                predicted_answer_group_index]
            for rule_spec in predicted_answer_group.rule_specs:
                if rule_spec.rule_type == exp_domain.RULE_TYPE_CLASSIFIER:
                    best_matched_rule_spec_index = classifier_rule_spec_index
                    break
            best_matched_answer_group = predicted_answer_group
            best_matched_answer_group_index = predicted_answer_group_index
            return {
                'outcome': best_matched_answer_group.outcome.to_dict(),
                'answer_group_index': best_matched_answer_group_index,
                'rule_spec_index': best_matched_rule_spec_index,
            }
        else:
            return None

    return None


def handle_trainable_states(exploration, state_names):
    """Creates ClassifierTrainingJobModel instances for all the state names
    passed into the function. If this function is called with version number 1,
    we are creating jobs for all trainable states in the exploration. Otherwise,
    a new job is being created for the states where retraining is required.

    Args:
        exploration: Exploration. The Exploration domain object.
        state_names: list(str). List of state names.
    """
    job_dicts_list = []
    exp_id = exploration.id
    exp_version = exploration.version
    for state_name in state_names:
        state = exploration.states[state_name]
        training_data = state.get_training_data()
        interaction_id = state.interaction.id
        algorithm_id = feconf.INTERACTION_CLASSIFIER_MAPPING[
            interaction_id]['algorithm_id']
        next_scheduled_check_time = datetime.datetime.utcnow()
        # Validate the job.
        dummy_classifier_training_job = classifier_domain.ClassifierTrainingJob(
            'job_id_dummy', algorithm_id, interaction_id, exp_id, exp_version,
            next_scheduled_check_time, state_name,
            feconf.TRAINING_JOB_STATUS_NEW, training_data)
        dummy_classifier_training_job.validate()

        job_dicts_list.append({
            'algorithm_id': algorithm_id,
            'interaction_id': interaction_id,
            'exp_id': exp_id,
            'exp_version': exp_version,
            'state_name': state_name,
            'training_data': training_data,
            'status': feconf.TRAINING_JOB_STATUS_NEW
        })

    # Create all the classifier training jobs.
    job_ids = classifier_models.ClassifierTrainingJobModel.create_multi(
        job_dicts_list)

    # Create mapping for each job. For TrainingJobExplorationMapping, we can
    # append Domain objects to send to the job_exploration_mappings dict because
    # we know all the attributes required for creating the Domain object unlike
    # ClassifierTrainingJob class where we don't know the job_id.
    job_exploration_mappings = []
    for job_id_index, job_id in enumerate(job_ids):
        job_exploration_mapping = (
            classifier_domain.TrainingJobExplorationMapping(
                job_dicts_list[job_id_index]['exp_id'],
                job_dicts_list[job_id_index]['exp_version'],
                job_dicts_list[job_id_index]['state_name'],
                job_id))
        job_exploration_mapping.validate()
        job_exploration_mappings.append(job_exploration_mapping)

    classifier_models.TrainingJobExplorationMappingModel.create_multi(
        job_exploration_mappings)


def handle_non_retrainable_states(exploration, state_names,
                                  new_to_old_state_names):
    """Creates new TrainingJobExplorationMappingModel instances for all the
    state names passed into the function. The mapping is created from the
    state in the new version of the exploration to the ClassifierTrainingJob of
    the state in the older version of the exploration. If there's been a change
    in the state name, we retrieve the old state name and create the mapping
    accordingly.
    This method is called only from exp_services._save_exploration() method and
    is never called from exp_services._create_exploration().
    In this method, the current_state_name refers to the name of the state in
    the current version of the exploration whereas the old_state_name refers to
    the name of the state in the previous version of the exploration.

    Args:
        exploration: Exploration. The Exploration domain object.
        state_names: list(str). List of state names.
        new_to_old_state_names: dict. Dict mapping new state names to their
            corresponding state names in previous version.

    Raises:
        Exception. This method should not be called by exploration with version
            number 1.
    """
    exp_id = exploration.id
    current_exp_version = exploration.version
    old_exp_version = current_exp_version - 1
    if old_exp_version <= 0:
        raise Exception(
            'This method should not be called by exploration with version '
            'number %s' % (current_exp_version))

    state_names_to_retrieve = []
    for current_state_name in state_names:
        old_state_name = new_to_old_state_names[current_state_name]
        state_names_to_retrieve.append(old_state_name)
    classifier_training_jobs = get_classifier_training_jobs(
        exp_id, old_exp_version, state_names_to_retrieve)

    job_exploration_mappings = []
    for index, classifier_training_job in enumerate(classifier_training_jobs):
        if classifier_training_job is None:
            logging.error(
                'The ClassifierTrainingJobModel for the %s state of Exploration'
                ' with exp_id %s and exp_version %s does not exist.' % (
                    state_names_to_retrieve[index], exp_id, old_exp_version))
            continue
        new_state_name = state_names[index]
        job_exploration_mapping = (
            classifier_domain.TrainingJobExplorationMapping(
                exp_id, current_exp_version, new_state_name,
                classifier_training_job.job_id))
        job_exploration_mapping.validate()
        job_exploration_mappings.append(job_exploration_mapping)

    classifier_models.TrainingJobExplorationMappingModel.create_multi(
        job_exploration_mappings)


def get_classifier_from_model(classifier_data_model):
    """Gets a classifier domain object from a classifier data model.

    Args:
        classifier_data_model: Classifier data model instance in datastore.

    Returns:
        classifier: Domain object for the classifier.
    """
    return classifier_domain.ClassifierData(
        classifier_data_model.id, classifier_data_model.exp_id,
        classifier_data_model.exp_version_when_created,
        classifier_data_model.state_name, classifier_data_model.algorithm_id,
        classifier_data_model.classifier_data,
        classifier_data_model.data_schema_version)


def get_classifier_by_id(classifier_id):
    """Gets a classifier from a classifier id.

    Args:
        classifier_id: str. ID of the classifier.

    Returns:
        classifier: Domain object for the classifier.

    Raises:
        Exception: Entity for class ClassifierDataModel with id not found.
    """
    classifier_data_model = classifier_models.ClassifierDataModel.get(
        classifier_id)
    classifier = get_classifier_from_model(classifier_data_model)
    return classifier


def create_classifier(job_id, classifier_data):
    """Creates classifier data model in the datastore given a classifier
       domain object.

    Args:
        job_id: str. ID of the ClassifierTrainingJob corresponding to the
            classifier.
        classifier_data: dict. The trained classifier data.

    Returns:
        classifier_id: str. ID of the classifier.

    Raises:
        Exception. The ClassifierDataModel corresponding to the job already
            exists.
        Exception. The algorithm_id of the job does not exist in the Interaction
            Classifier Mapping.
    """
    classifier_data_model = classifier_models.ClassifierDataModel.get(
        job_id, strict=False)
    if classifier_data_model is not None:
        raise Exception(
            'The ClassifierDataModel corresponding to the job already exists.')

    classifier_training_job = get_classifier_training_job_by_id(job_id)
    state_name = classifier_training_job.state_name
    exp_id = classifier_training_job.exp_id
    exp_version = classifier_training_job.exp_version
    algorithm_id = classifier_training_job.algorithm_id
    interaction_id = classifier_training_job.interaction_id
    data_schema_version = None
    if feconf.INTERACTION_CLASSIFIER_MAPPING[interaction_id][
            'algorithm_id'] == algorithm_id:
        data_schema_version = feconf.INTERACTION_CLASSIFIER_MAPPING[
            interaction_id]['current_data_schema_version']
    if data_schema_version is None:
        raise Exception(
            'The algorithm_id of the job does not exist in the Interaction '
            'Classifier Mapping.')

    classifier = classifier_domain.ClassifierData(
        job_id, exp_id, exp_version, state_name, algorithm_id,
        classifier_data, data_schema_version)
    classifier.validate()

    classifier_id = classifier_models.ClassifierDataModel.create(
        classifier.id, classifier.exp_id,
        classifier.exp_version_when_created,
        classifier.state_name, classifier.algorithm_id,
        classifier.classifier_data, classifier.data_schema_version)

    return classifier_id


def delete_classifier(classifier_id):
    """Deletes classifier data model in the datastore given classifier_id.

    Args:
        classifier_id: str. ID of the classifier.
    """
    classifier_data_model = classifier_models.ClassifierDataModel.get(
        classifier_id)
    classifier_data_model.delete()


def get_classifier_training_job_from_model(classifier_training_job_model):
    """Gets a classifier training job domain object from a classifier
    training job model.

    Args:
        classifier_training_job_model: ClassifierTrainingJobModel. Classifier
            training job instance in datastore.

    Returns:
        classifier_training_job: ClassifierTrainingJob. Domain object for the
            classifier training job.
    """
    return classifier_domain.ClassifierTrainingJob(
        classifier_training_job_model.id,
        classifier_training_job_model.algorithm_id,
        classifier_training_job_model.interaction_id,
        classifier_training_job_model.exp_id,
        classifier_training_job_model.exp_version,
        classifier_training_job_model.next_scheduled_check_time,
        classifier_training_job_model.state_name,
        classifier_training_job_model.status,
        classifier_training_job_model.training_data)

def get_classifier_training_job_by_id(job_id):
    """Gets a classifier training job by a job_id.

    Args:
        job_id: str. ID of the classifier training job.

    Returns:
        classifier_training_job: ClassifierTrainingJob. Domain object for the
            classifier training job.

    Raises:
        Exception: Entity for class ClassifierTrainingJobModel with id not
            found.
    """
    classifier_training_job_model = (
        classifier_models.ClassifierTrainingJobModel.get(job_id))
    classifier_training_job = get_classifier_training_job_from_model(
        classifier_training_job_model)
    return classifier_training_job


def create_classifier_training_job(algorithm_id, interaction_id, exp_id,
                                   exp_version, state_name, training_data,
                                   status):
    """Creates a ClassifierTrainingJobModel in data store.

    Args:
        algorithm_id: str. ID of the algorithm used to generate the model.
        interaction_id: str. ID of the interaction to which the algorithm
            belongs.
        exp_id: str. ID of the exploration.
        exp_version: int. The exploration version at the time
            this training job was created.
        state_name: str. The name of the state to which the classifier
            belongs.
        training_data: dict. The data used in training phase.
        status: str. The status of the training job (NEW by default).

    Returns:
        job_id: str. ID of the classifier training job.
    """
    next_scheduled_check_time = datetime.datetime.utcnow()
    dummy_classifier_training_job = classifier_domain.ClassifierTrainingJob(
        'job_id_dummy', algorithm_id, interaction_id, exp_id, exp_version,
        next_scheduled_check_time, state_name, status, training_data)
    dummy_classifier_training_job.validate()
    job_id = classifier_models.ClassifierTrainingJobModel.create(
        algorithm_id, interaction_id, exp_id, exp_version,
        next_scheduled_check_time, training_data, state_name, status)
    return job_id


def _update_classifier_training_jobs_status(job_ids, status):
    """Checks for the existence of the model and then updates it.

    Args:
        job_id: list(str). list of ID of the ClassifierTrainingJob domain
            objects.
        status: str. The status to which the job needs to be updated.

    Raises:
        Exception. The ClassifierTrainingJobModel corresponding to the job_id
            of the ClassifierTrainingJob does not exist.
    """
    classifier_training_job_models = (
        classifier_models.ClassifierTrainingJobModel.get_multi(job_ids))

    for index, job_id in enumerate(job_ids):
        if classifier_training_job_models[index] is None:
            raise Exception(
                'The ClassifierTrainingJobModel corresponding to the job_id '
                'of the ClassifierTrainingJob does not exist.')

        initial_status = classifier_training_job_models[index].status
        if status not in (
                feconf.ALLOWED_TRAINING_JOB_STATUS_CHANGES[initial_status]):
            raise Exception(
                'The status change %s to %s is not valid.' % (
                    initial_status, status))

        classifier_training_job = get_classifier_training_job_by_id(
            job_id)
        classifier_training_job.update_status(status)
        classifier_training_job.validate()

        classifier_training_job_models[index].status = status

    classifier_models.ClassifierTrainingJobModel.put_multi(
        classifier_training_job_models)


def mark_training_job_complete(job_id):
    """Updates the training job's status to complete.

    Args:
        job_id: str. ID of the ClassifierTrainingJob.
    """
    _update_classifier_training_jobs_status(
        [job_id], feconf.TRAINING_JOB_STATUS_COMPLETE)


def mark_training_jobs_failed(job_ids):
    """Updates the training job's status to failed.

    Args:
        job_ids: list(str). list of ID of the ClassifierTrainingJobs.
    """
    _update_classifier_training_jobs_status(
        job_ids, feconf.TRAINING_JOB_STATUS_FAILED)


def mark_training_job_pending(job_id):
    """Updates the training job's status to pending.

    Args:
        job_id: str. ID of the ClassifierTrainingJob.
    """
    _update_classifier_training_jobs_status(
        [job_id], feconf.TRAINING_JOB_STATUS_PENDING)


def _update_job_next_scheduled_check_time(job_id):
    """Updates the next scheduled check time of job.

    Args:
        job_id: str. ID of the ClassifierTrainingJob.
    """
    classifier_training_job_model = (
        classifier_models.ClassifierTrainingJobModel.get(job_id))

    if not classifier_training_job_model:
        raise Exception(
            'The ClassifierTrainingJobModel corresponding to the job_id '
            'of the ClassifierTrainingJob does not exist.')

    classifier_training_job_model.next_scheduled_check_time = (
        datetime.datetime.utcnow() + datetime.timedelta(
            minutes=feconf.CLASSIFIER_JOB_TTL_MINS))
    classifier_training_job_model.put()


def fetch_next_job():
    """Gets next job model in the job queue.

    Returns:
        ClassifierTrainingJob. Domain object of the next training Job.
    """
    classifier_training_jobs = []
    # Initially the cursor for query is set to None.
    cursor = None
    valid_jobs = []
    failed_job_ids = []

    while len(valid_jobs) == 0:
        classifier_training_jobs, cursor, more = (
            classifier_models.ClassifierTrainingJobModel.query_training_jobs(
                cursor))
        for training_job in classifier_training_jobs:
            if(training_job.status == (
                    feconf.TRAINING_JOB_STATUS_PENDING)):
                failed_job_ids.append(training_job.id)
            else:
                valid_jobs.append(training_job)
        if not more:
            break

    if len(failed_job_ids) > 0:
        mark_training_jobs_failed(failed_job_ids)

    if len(valid_jobs) > 0:
        next_job = get_classifier_training_job_from_model(valid_jobs[0])
        _update_job_next_scheduled_check_time(next_job.job_id)
    else:
        next_job = None
    return next_job


def delete_classifier_training_job(job_id):
    """Deletes classifier training job model in the datastore given job_id.

    Args:
        job_id: str. ID of the classifier training job.
    """
    classifier_training_job_model = (
        classifier_models.ClassifierTrainingJobModel.get(job_id))
    if classifier_training_job_model is not None:
        classifier_training_job_model.delete()


def get_classifier_training_jobs(exp_id, exp_version, state_names):
    """Gets the classifier training job object from the exploration attributes.

    Args:
        exp_id: str. ID of the exploration.
        exp_version: int. The exploration version.
        state_names: list(str). The state names for which we retrieve the job.

    Returns:
        list(ClassifierTrainingJob). Domain objects for the Classifier training
            job model.
    """
    training_job_exploration_mapping_models = (
        classifier_models.TrainingJobExplorationMappingModel.get_models(
            exp_id, exp_version, state_names))
    job_ids = []
    for mapping_model in training_job_exploration_mapping_models:
        if mapping_model is None:
            continue
        job_ids.append(mapping_model.job_id)
    classifier_training_job_models = (
        classifier_models.ClassifierTrainingJobModel.get_multi(job_ids))
    classifier_training_jobs = []
    for job_model in classifier_training_job_models:
        classifier_training_jobs.append(get_classifier_training_job_from_model(
            job_model))

    # Backfill None's to maintain indexes.
    for index, mapping_model in enumerate(
            training_job_exploration_mapping_models):
        if mapping_model is None:
            classifier_training_jobs.insert(index, None)
    return classifier_training_jobs
