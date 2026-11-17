import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_catalog_mesen import empty_startup_failure,script_watchdog_failure


class CatalogStartupTests(unittest.TestCase):
    def check(self,message,elapsed=1,output=''):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);log=root/'runner.log';log.write_text(message)
            config=root/'config.lua';config.write_text('return {}')
            emulator=root/'emulator.log';emulator.write_text(output)
            os.utime(config,(1000,1000));os.utime(emulator,(1000+elapsed,1000+elapsed))
            return empty_startup_failure(log,root)

    def test_empty_immediate_exit_is_retryable(self):
        for code in (4294967295,3221226505):
            self.assertTrue(self.check(f'Mesen exited {code} without a result'))

    def test_runtime_crash_is_not_retryable(self):
        self.assertFalse(self.check('Mesen exited 4294967295 without a result',elapsed=30))

    def test_reported_error_is_not_retryable(self):
        self.assertFalse(self.check('Mesen exited 4294967295 without a result',output='Lua error'))

    def test_assertion_is_not_retryable(self):
        self.assertFalse(self.check('AssertionError: Third planet is on the wrong side'))

    def test_unexpected_exit_is_not_retryable(self):
        self.assertFalse(self.check('Mesen exited 123 without a result'))

    def test_only_exact_host_deadline_gets_a_serial_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);result=root/'result.txt'
            result.write_text('verify_palette_mesen.lua:28: Maximum execution time (1 seconds) exceeded.\nFAIL\n')
            self.assertTrue(script_watchdog_failure(root))
            result.write_text('Wrong palette\nFAIL\n')
            self.assertFalse(script_watchdog_failure(root))
            result.write_text('Maximum execution time (1 seconds) exceeded.\nWrong planet\nFAIL\n')
            self.assertFalse(script_watchdog_failure(root))


if __name__=='__main__':unittest.main()
