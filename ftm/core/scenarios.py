from . import utils
from .utils import log, get_parameter_table, get_timelines_parameters
from .model import SimulateTakeOff

import numpy as np

class ScenarioRunner:
  def __init__(self):
    self.groups = None
    self.metrics = None

  def simulate_all_scenarios(self):
    parameter_table = get_parameter_table()
    timelines_parameters = get_timelines_parameters()

    groups = []

    scenarios = self.simulate_scenario_group(parameter_table)
    log.info('')
    groups.append(ScenarioGroup('normal', scenarios, parameter_table))

    for timeline in timelines_parameters:
      parameters = timelines_parameters[timeline]

      timeline_table = parameter_table.copy()

      timeline_table.loc['full_automation_requirements_training', 'Conservative'] = parameters['Full automation requirements']
      timeline_table.loc['full_automation_requirements_training', 'Best guess']   = parameters['Full automation requirements']
      timeline_table.loc['full_automation_requirements_training', 'Aggressive']   = parameters['Full automation requirements']

      if timeline == 'Very short timelines':
        runtime_requirements = parameter_table.loc['full_automation_requirements_runtime', 'Aggressive']
      elif timeline == 'Med timelines':
        runtime_requirements = parameter_table.loc['full_automation_requirements_runtime', 'Best guess']
      elif timeline == 'Very long timelines':
        runtime_requirements = parameter_table.loc['full_automation_requirements_runtime', 'Conservative']
      else:
        raise Exception(f'Unknown timeline: "{timeline}"')

      timeline_table.loc['full_automation_requirements_runtime', 'Conservative'] = runtime_requirements
      timeline_table.loc['full_automation_requirements_runtime', 'Best guess']   = runtime_requirements
      timeline_table.loc['full_automation_requirements_runtime', 'Aggressive']   = runtime_requirements

      timeline_table.loc['flop_gap_training', 'Conservative'] = parameters['Long FLOP gap']
      timeline_table.loc['flop_gap_training', 'Best guess']   = parameters['Med FLOP gap']
      timeline_table.loc['flop_gap_training', 'Aggressive']   = parameters['Short FLOP gap']

      log.indent()
      scenarios = self.simulate_scenario_group(timeline_table)
      groups.append(ScenarioGroup(timeline, scenarios, timeline_table, parameters['Full automation requirements']))
      log.deindent()

      log.info('')

    self.groups = groups

    return groups

  def simulate_scenario_group(self, parameter_table, simulation_type = 'compare'):
    # Define parameters
    med_params = {
      parameter : row['Best guess']
      for parameter, row in parameter_table.iterrows()
    }

    if simulation_type == 'compare':

      low_params = {
          parameter : row['Conservative'] \
                      if not np.isnan(row['Conservative']) \
                      and row["Compare?"] == 'Y'
                      else row['Best guess']\
          for parameter, row in parameter_table.iterrows()
      }

      high_params = {
          parameter : row['Aggressive'] \
                      if not np.isnan(row['Aggressive']) \
                      and row["Compare?"] == 'Y'
                      else row['Best guess']\
          for parameter, row in parameter_table.iterrows()
      }

      low_value = 'Conservative'
      med_value = 'Best guess'
      high_value = 'Aggressive'

    else:
      row = parameter_table.loc[exploration_target, :]

      low_params = med_params.copy()
      low_params[exploration_target] = row['Conservative']

      high_params = med_params.copy()
      high_params[exploration_target] = row['Aggressive']

      low_value = row['Conservative']
      med_value = row['Best guess']
      high_value = row['Aggressive']

    # Run simulations
    log.info('Running simulations...')

    low_params['dynamic_t_end'] = True
    med_params['dynamic_t_end'] = True
    high_params['dynamic_t_end'] = True

    log.info('  Conservative simulation')
    low_model = SimulateTakeOff(**low_params)
    low_model.run_simulation()

    log.info('  Best guess simulation')
    med_model = SimulateTakeOff(**med_params)
    med_model.run_simulation()

    log.info('  Aggressive simulation')
    high_model = SimulateTakeOff(**high_params)
    high_model.run_simulation()

    # hacky
    if self.metrics is None:
      self.metrics = [MetricDescription(name, name) for name in med_model.get_takeoff_metrics()]

    scenarios = [
      Scenario('Conservative', low_model,  low_params),
      Scenario('Best guess',   med_model,  med_params),
      Scenario('Aggressive',   high_model, high_params),
    ]

    return scenarios

class ScenarioGroup:
  def __init__(self, name, scenarios, parameter_table, full_automation_reqs = None):
    self.name = name
    self.scenarios = scenarios
    self.parameter_table = parameter_table
    self.full_automation_reqs = full_automation_reqs
    self.reqs_label = f'{full_automation_reqs:.0e}'.replace('+', '') if (full_automation_reqs is not None) else '--'

  def __getitem__(self, index):
    return self.scenarios[index]

  def __len__(self):
    return len(self.scenarios)

class Scenario:
  def __init__(self, name, model, params):
    self.name    = name
    self.model   = model
    self.params  = params
    self.metrics = [Metric(name, value[0]) for name, value in model.get_takeoff_metrics().items()]

class MetricDescription:
  def __init__(self, name, meaning):
    self.name = name
    self.meaning = meaning

class Metric:
  def __init__(self, name, value):
    self.name = name
    self.value = value

