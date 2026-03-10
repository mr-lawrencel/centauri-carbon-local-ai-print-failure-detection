import unittest
import sys
import os

# Add the watcher-app directory to the path so we can import the modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'watcher-app')))

# Mock environment variables before importing Config
os.environ["PRINTER_IP"] = "127.0.0.1"
os.environ["MAINBOARD_ID"] = "mock_id"

from vision import extract_confidence_score

class TestVision(unittest.TestCase):
    def test_extract_confidence_score_pure_number(self):
        self.assertEqual(extract_confidence_score("85"), 85)
    
    def test_extract_confidence_score_with_text(self):
        self.assertEqual(extract_confidence_score("The confidence score is 42%."), 42)
        self.assertEqual(extract_confidence_score("90% failure detected"), 90)
        self.assertEqual(extract_confidence_score("Result: 15"), 15)
    
    def test_extract_confidence_score_no_number(self):
        self.assertIsNone(extract_confidence_score("No failure found"))
    
    def test_extract_confidence_score_multiple_numbers(self):
        # Should pick the first number found
        self.assertEqual(extract_confidence_score("80 (threshold was 70)"), 80)

if __name__ == '__main__':
    unittest.main()
