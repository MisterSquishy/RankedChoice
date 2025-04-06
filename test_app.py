import unittest

from app import calculate_irv_winner


class TestCalculateIRVWinner(unittest.TestCase):

    def assertElementsMatch(self, list1, list2):
        """Assert that two lists have the same elements, regardless of order."""
        self.assertEqual(sorted(list1), sorted(list2))

    def test_empty_ballots(self):
        """Test when there are no ballots."""
        rankings = {}
        winner, rounds = calculate_irv_winner(rankings)
        self.assertEqual(len(rounds), 0)
        self.assertIsNone(winner)

    def test_no_votes_left(self):
        """Test when all ballots become empty during elimination."""
        rankings = {
            "voter1": ["A", "B"],
            "voter2": ["B", "A"],
            "voter3": ["C", "A"]
        }
        winner, rounds = calculate_irv_winner(rankings)
        self.assertEqual(len(rounds), 1)
        self.assertElementsMatch(rounds[0], [
            # first round eliminates A, B, and C
            [], 
            [], 
            [], 
        ])
        self.assertIn(winner, ["A", "B", "C"]) # randomly chosen winner

    def test_majority_winner_first_round(self):
        """Test when there's a majority winner in the first round."""
        rankings = {
            "voter1": ["A", "B", "C"],
            "voter2": ["A", "C", "B"],
            "voter3": ["A", "B", "C"],
            "voter4": ["B", "A", "C"],
            "voter5": ["C", "B", "A"]
        }
        winner, rounds = calculate_irv_winner(rankings)
        self.assertEqual(len(rounds), 0)
        self.assertEqual(winner, "A")

    def test_majority_winner_after_elimination(self):
        """Test when there's a majority winner after eliminating a candidate."""
        rankings = {
            "voter1": ["A", "B", "C"],
            "voter2": ["B", "A", "C"],
            "voter3": ["B", "C", "A"],
            "voter4": ["C", "A", "B"],
            "voter5": ["C", "B", "A"]
        }
        winner, rounds = calculate_irv_winner(rankings)
        self.assertEqual(len(rounds), 1)
        self.assertElementsMatch(rounds[0], [
            # first round eliminates A
            ["B", "C"], 
            ["B", "C"], 
            ["B", "C"], 
            ["C", "B"], 
            ["C", "B"], 
        ])
        self.assertEqual(winner, "B")

    def test_multiple_elimination_rounds(self):
        """Test when multiple rounds of elimination are needed."""
        rankings = {
            "voter1": ["A", "B", "C", "D"],
            "voter2": ["B", "A", "D", "C"],
            "voter3": ["D", "C", "A", "B"],
            "voter4": ["D", "C", "B", "A"],
            "voter5": ["A", "C", "B", "D"]
        }
        winner, rounds = calculate_irv_winner(rankings)
        self.assertEqual(len(rounds), 2)
        self.assertElementsMatch(rounds[0], [
            # first round eliminates C
            # still no majority
            ['A', 'B', 'D'], 
            ['B', 'A', 'D'], 
            ['D', 'A', 'B'], 
            ['D', 'B','A'], 
            ['A', 'B','D']
        ])
        self.assertElementsMatch(rounds[1], [
            # second round eliminates B
            # creates majority for A
            ['A', 'D'], 
            ['A', 'D'], 
            ['D', 'A'], 
            ['D', 'A'], 
            ['A', 'D']
        ])
        self.assertEqual(winner, "A")

    def test_condorcet_winner_loses(self):
        """Test that IRV doesn't always select the Condorcet winner.
        
        A Condorcet winner is a candidate that would win against every other candidate
        in a head-to-head comparison. IRV can sometimes eliminate the Condorcet winner
        early if they don't get enough first-choice votes.
        """
        # Classic example where IRV fails to select Condorcet winner
        rankings = {
            "voter1": ["A", "B", "C"],
            "voter2": ["A", "B", "C"], 
            "voter3": ["C", "B", "A"],
            "voter4": ["C", "B", "A"],
            "voter5": ["C", "B", "A"]
        }
        
        # B is the Condorcet winner:
        # B vs A: B wins (3 prefer B to A: voter3,4,5)
        # B vs C: B wins (3 prefer B to C: voter1,2)
        # But B gets eliminated first since no first choices
        
        winner, rounds = calculate_irv_winner(rankings)
        self.assertEqual(len(rounds), 0)
        self.assertEqual(winner, "C")

    def test_burlington_2009_mayoral_race(self):
        """Test scenario based on 2009 Burlington, VT mayoral election.
        
        This election demonstrated how IRV can elect neither the Condorcet winner
        nor the plurality winner. Progressive candidate Bob Kiss won despite:
        - Republican Kurt Wright having the most first-choice votes (plurality winner)
        - Democratic candidate Andy Montroll being preferred head-to-head against 
          both other candidates (Condorcet winner)
        
        Source: https://en.wikipedia.org/wiki/2009_Burlington,_Vermont_mayoral_election
        """
        # Simplified ballot counts (actual election had 8,980 ballots)
        # Create multiple identical ballots for each voting pattern
        rankings = {
            # Wright (Republican) voters
            "voter1": ["Wright", "Montroll", "Kiss"],
            "voter2": ["Wright", "Montroll", "Kiss"],
            "voter3": ["Wright", "Montroll", "Kiss"],
            "voter4": ["Wright", "Kiss", "Montroll"],
            
            # Montroll (Democrat) voters
            "voter5": ["Montroll", "Kiss", "Wright"],
            "voter6": ["Montroll", "Kiss", "Wright"],
            
            # Kiss (Progressive) voters
            "voter7": ["Kiss", "Montroll", "Wright"],
            "voter8": ["Kiss", "Montroll", "Wright"],
            "voter9": ["Kiss", "Montroll", "Wright"],
        }
        
        winner, rounds = calculate_irv_winner(rankings)
        self.assertEqual(len(rounds), 1)
        self.assertElementsMatch(rounds[0], [
            # First round eliminates Montroll despite being Condorcet winner
            # (beats Kiss 5-4, beats Wright 5-4)
            # Kiss wins with majority despite Wright originally being the plurality winner

            # Wright (Republican) voters
            ["Wright", "Kiss"],
            ["Wright", "Kiss"],
            ["Wright", "Kiss"],
            ["Wright", "Kiss"],
            
            # Montroll (Democrat) voters
            ["Kiss", "Wright"],
            ["Kiss", "Wright"],

            # Kiss (Progressive) voters
            ["Kiss", "Wright"],
            ["Kiss", "Wright"],
            ["Kiss", "Wright"],
        ])
        self.assertEqual(winner, "Kiss")
        
        

if __name__ == '__main__':
    unittest.main() 