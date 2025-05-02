import os
import sys
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the function to test
from service.scheduler.scheduler import build_metric_evaluator_cronjob
from service.utils.log import get_logger

logging = get_logger("TestBuildMetricEvaluatorCronJob")


class TestBuildMetricEvaluatorCronJob(unittest.TestCase):
    def setUp(self):
        with open('tests/fixtures/metric.yaml', 'r') as f:
            self.metric_yaml = f.read()
            self.metric = yaml.safe_load(self.metric_yaml)

        with open('tests/fixtures/generated-cronjob.yaml', 'r') as f:
            self.expected_cronjob_yaml = f.read()
            self.expected_cronjob = yaml.safe_load(self.expected_cronjob_yaml)

    def test_build_metric_evaluator_cronjob(self):
        cronjobs, status = build_metric_evaluator_cronjob(self.metric)

        # Verify the status
        self.assertEqual(status, "Success")

        # Verify that we got one CronJob back
        self.assertEqual(len(cronjobs), 1)

        generated_cronjob = cronjobs[0]

        self.maxDiff = None

        with open('generated.yaml', 'w') as f:
            yaml.dump(generated_cronjob, f)

        with open('expected.yaml', 'w') as f:
            yaml.dump(self.expected_cronjob, f)

        self.assertDictEqual(generated_cronjob, self.expected_cronjob)

    def test_build_metric_evaluator_cronjob_no_schedule(self):
        metric_no_schedule = self.metric.copy()
        del metric_no_schedule['spec']['cronSchedule']

        cronjobs, status = build_metric_evaluator_cronjob(metric_no_schedule)

        self.assertEqual(len(cronjobs), 0)
        self.assertEqual(status, "NoSchedule")

    @patch('service.scheduler.scheduler.logger')
    def test_build_metric_evaluator_cronjob_exception(self, mock_logger):
        incomplete_metric = {'metadata': {'name': 'test-metric'}}

        cronjobs, status = build_metric_evaluator_cronjob(incomplete_metric)

        self.assertEqual(len(cronjobs), 0)
        self.assertEqual(status, "Failed")

        mock_logger.error.assert_called_once()
