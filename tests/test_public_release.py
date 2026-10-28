"""Meaningful offline boundaries; no private assets or GPU packages required."""
import importlib.util,json,os,sys,unittest
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO));sys.path.insert(0,str(REPO/'implementation/tools'))
import release_config
import nailv_style3 as style
import nailv_expression_variation as variation
spec=importlib.util.spec_from_file_location('public_demo',REPO/'scripts/offline_demo.py');demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)

class PublicReleaseTests(unittest.TestCase):
    def test_distress_beats_calling(self):
        self.assertEqual(style.input_act('妈妈妈妈'),'calling')
        self.assertEqual(style.input_act('妈妈，我今天没考好。'),'comfort')
    def test_real_retriever_fictional_cards(self):
        rows=demo.run()
        self.assertEqual(rows[0]['candidate_ids'][0],'fictional-calling')
        self.assertEqual(rows[1]['candidate_ids'][0],'fictional-comfort')
        self.assertEqual(rows[2]['candidate_ids'][0],'fictional-celebrate')
    def test_cooldown_keeps_definition_available(self):
        history=[{'role':'assistant','content':'你又给我扣帽子。'}]
        self.assertTrue(variation.cooldown('你好',history))
        self.assertFalse(variation.cooldown('扣帽子是什么意思？',history))
    def test_project_path_rejects_escape(self):
        with self.assertRaises(ValueError):release_config.project_path('../outside')
    def test_critic_contract_is_offline(self):
        text=(REPO/'implementation/runtime/cosyvoice3/scripts/audio_critic.py').read_text(encoding='utf-8')
        self.assertIn("os.environ['CUDA_VISIBLE_DEVICES']='-1'",text)
        self.assertIn('not a validated',text.lower().replace('not listening or a validated','not a validated'))

if __name__=='__main__':unittest.main()
