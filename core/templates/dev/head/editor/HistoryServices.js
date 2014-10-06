// Copyright 2014 The Oppia Authors. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS-IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Services for the exploration history tab.
 *
 * @author wxyxinyu@gmail.com (Xinyu Wu)
 */

// Service for handling all interactions with the version history tree
oppia.factory('versionsTreeService', [function() {
  var _snapshots = null;
  var _treeParents = null;
  return {
    init: function(snapshotsData) {
      _treeParents = {};
      _snapshots = {};
      var numberOfVersions = snapshotsData.length;

      // Populate _snapshots so _snapshots[i] corresponds to version i
      for (var i = 0; i < numberOfVersions; i++) {
        _snapshots[i + 1] = snapshotsData[i];
      }

      // Generate the version tree of an exploration from its snapshots
      for (var versionNumber = 2; versionNumber <= numberOfVersions; versionNumber++) {
        if (_snapshots[versionNumber].commit_type == 'revert') {
          for (var i = 0; i < _snapshots[versionNumber].commit_cmds.length; i++) {
            if (_snapshots[versionNumber].commit_cmds[i].cmd == 'AUTO_revert_version_number') {
              _treeParents[versionNumber] =
                  _snapshots[versionNumber].commit_cmds[i].version_number;
            }
          }
        } else {
          _treeParents[versionNumber] = versionNumber - 1;
        }
      }
      _treeParents[1] = -1;
    },
    /**
     * Returns a object whose keys are the version number and whose value is
     * the parent of each version, where parent points to previous version
     * in general or reverted version if commit is a reversion.
     * The parent of the root (version 1) is -1.
     */
    getVersionTree: function() {
      if (_treeParents === null) {
        throw new Error('version tree not initialized.');
      }
      return _treeParents;
    },
    // Finds lowest common ancestor of v1 and v2 in the version tree.
    findLCA: function(v1, v2) {
      // Find paths from root to v1 and v2
      var pathToV1 = [];
      var pathToV2 = [];
      while (_treeParents[v1] != -1) {
        pathToV1.push(v1);
        if (_treeParents[v1] === undefined) {
          throw new Error('Could not find parent of ' + v1);
        }
        v1 = _treeParents[v1];
      }
      pathToV1.push(1);
      pathToV1.reverse();

      while (_treeParents[v2] != -1) {
        pathToV2.push(v2);
        if (_treeParents[v2] === undefined) {
          throw new Error('Could not find parent of ' + v2);
        }
        v2 = _treeParents[v2];
      }
      pathToV2.push(1);
      pathToV2.reverse();

      // Compare paths
      var maxIndex = Math.min(pathToV1.length, pathToV2.length) - 1;
      var lca = null;
      for (var i = maxIndex; i >= 0; i--) {
        if (pathToV1[i] == pathToV2[i]) {
          lca = pathToV1[i];
          break;
        }
      }
      return lca;
    },
    /**
     * Returns the change list of a version of the exploration.
     * Should be called only after getVersionTree is called to initialize
     * _snapshots. Should not be called to retrieve change list of version 1.
     * Returns a list of objects with keys depending on type of commit:
     *  - 'cmd': type of commit; 'add_state', 'rename_state', 'delete_state',
     *           'edit_state_property' or 'revert'
     * for 'add_state' and 'delete_state':
     *  - 'state_name': added or deleted state name
     * for 'rename_state':
     *  - 'new_state_name': new state name
     *  - 'old_state_name': old state name
     * for 'edit_state_property': (edits to state content or rules)
     *  - 'new_value': object which represents new version of state
     *  - 'old_value': object which represents old version of state
     *  - 'state_name': name of state which was changed
     * for 'revert':
     *  - 'version_number': version number reverted to
     */
    getChangeList: function(version) {
      if (_snapshots === null) {
        throw new Error('snapshots is not initialized');
      }
      else if (version == 1) {
        throw new Error('Tried to retrieve change list of version 1');
      }
      return angular.copy(_snapshots[version].commit_cmds);
    }
  };
}]);


oppia.factory('compareVersionsService', ['$http', '$q', 'versionsTreeService',
    'explorationData', function(
    $http, $q, versionsTreeService, explorationData) {
  var STATE_PROPERTY_ADDED = 'added';
  var STATE_PROPERTY_DELETED = 'deleted';
  var STATE_PROPERTY_CHANGED = 'changed';
  var STATE_PROPERTY_UNCHANGED = 'unchanged';
  var _maxId = 0;

  // Functions to assign ids to states
  function _resetMaxId() {
    _maxId = 0;
  }
  function _generateNewId() {
    _maxId++;
    return _maxId;
  }

  /**
   * A helper function for getStatesDiff. Tracks changes from v1 to v2 and
   * modifies stateIds and stateData accordingly.
   * v1 must be an ancestor of v2.
   *
   * stateIds is an object whose keys are the newest state name and whose
   * values are the assigned state id.
   * stateData an object whose keys are state IDs and whose value is an object
   * with these keys:
   *  - 'newestStateName': the latest name of the state
   *  - 'originalStateName': the first encountered name for the state
   *  - 'stateProperty': 'changed', 'unchanged', 'added' or 'deleted'
   * directionForwards is true if changes are compared in increasing version
   * number, and false if changes are compared in decreasing version number.
   */
  function _trackChanges(v1, v2, stateIds, stateData, directionForwards) {
    var _treeParents = versionsTreeService.getVersionTree();

    var nodeList = [];
    while (v2 != v1) {
      nodeList.push(v2);
      v2 = _treeParents[v2];
    }
    if (directionForwards) {
      nodeList.reverse();
    }

    for (var i = 0; i < nodeList.length; i++) {
      var changeList = versionsTreeService.getChangeList(nodeList[i]);
      for (var j = 0; j < changeList.length; j++) {
        var change = changeList[j];
        if ((directionForwards && change.cmd == 'add_state') ||
            (!directionForwards && change.cmd == 'delete_state')) {
          if (!stateIds.hasOwnProperty(change.state_name)) {
            var newId = _generateNewId();
            stateIds[change.state_name] = newId;
          }
          var currentStateId = stateIds[change.state_name];
          if (stateData.hasOwnProperty(currentStateId) &&
              stateData[currentStateId].stateProperty == STATE_PROPERTY_DELETED) {
            stateData[currentStateId].stateProperty = STATE_PROPERTY_CHANGED;
            stateData[currentStateId].newestStateName = change.state_name;
          } else {
            stateData[stateIds[change.state_name]] = {
              'newestStateName': change.state_name,
              'originalStateName': change.state_name,
              'stateProperty': STATE_PROPERTY_ADDED
            };
          }
        } else if ((directionForwards && change.cmd == 'delete_state') ||
            (!directionForwards && change.cmd == 'add_state')) {
          if (stateData[stateIds[change.state_name]].stateProperty == STATE_PROPERTY_ADDED) {
            stateData[stateIds[change.state_name]].stateProperty = STATE_PROPERTY_CHANGED;
          } else {
            stateData[stateIds[change.state_name]].stateProperty = STATE_PROPERTY_DELETED;
          }
        } else if (change.cmd == 'rename_state') {
          var newStateName = null;
          var oldStateName = null;
          if (directionForwards) {
            newStateName = change.new_state_name;
            oldStateName = change.old_state_name;
          } else {
            newStateName = change.old_state_name;
            oldStateName = change.new_state_name;
          }
          stateIds[newStateName] = stateIds[oldStateName];
          delete stateIds[oldStateName];
          stateData[stateIds[newStateName]].newestStateName = newStateName;
        } else if (change.cmd == 'edit_state_property') {
          if (stateData[stateIds[change.state_name]].stateProperty == STATE_PROPERTY_UNCHANGED) {
            stateData[stateIds[change.state_name]].stateProperty = STATE_PROPERTY_CHANGED;
          }
        }
      }
    }
  }
  return {
    /**
     * Summarize changes to each state between v1 and v2.
     * Returns a promise for an object whose keys are state IDs (assigned
     * within the function) and whose value is an object with these keys:
     *  - 'newestStateName': the latest name of the state
     *  - 'originalStateName': the first encountered name for the state
     *  - 'stateProperty': 'changed', 'unchanged', 'added' or 'deleted'
     *
     * Should be called after versionsTreeService.generateVersionTree is called.
     * Should satisfy v1 < v2.
     */
    getStatesDiff: function(v1, v2) {
      if (v1 > v2) throw new Error('Tried to compare v1 > v2.');
      var explorationDataUrl = '/createhandler/data/' +
        explorationData.explorationId + '?v=';
      return $q.all({
        'v1Data': $http.get(explorationDataUrl + v1),
        'v2Data': $http.get(explorationDataUrl + v2)
      }).then(function(response) {
        var v1States = response.v1Data.data.states,
            v2States = response.v2Data.data.states;

        // Find initial stateIds and originalStateNames
        var statesData = {};
        var stateIds = {};
        _resetMaxId();
        for (var stateName in v1States) {
          var stateId = _generateNewId();
          statesData[stateId] = {
            'newestStateName': stateName,
            'originalStateName': stateName,
            'stateProperty': STATE_PROPERTY_UNCHANGED
          };
          stateIds[stateName] = stateId;
        }

        // Find changes from v1 to LCA and from LCA to v2
        var lca = versionsTreeService.findLCA(v1, v2);
        _trackChanges(lca, v1, stateIds, statesData, false);
        _trackChanges(lca, v2, stateIds, statesData, true);

        // Remove changes back to original
        for (var stateId in statesData) {
          if (statesData[stateId].stateProperty == STATE_PROPERTY_CHANGED &&
              v1States.hasOwnProperty(statesData[stateId].originalStateName) &&
              v2States.hasOwnProperty(statesData[stateId].newestStateName) &&
              angular.equals(v1States[statesData[stateId].originalStateName],
                v2States[statesData[stateId].newestStateName])) {
            statesData[stateId].stateProperty = STATE_PROPERTY_UNCHANGED;
          }
        }

        return statesData;
      });
    }
  };
}]);
