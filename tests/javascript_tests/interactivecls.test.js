const {
  program,
  load_configuration,
  LEDS,
  zeroPad,
  generateLEDList,
  led_to_arduino_string,
  assignletter,
  selectedindex,
  renderTable,
  changeCurrentSet,
  copySetToTable,
  writeStatus,
  generateDefaultExperiment,
  isJSONfile,
  isDirectory,
  getfilelist,
  get_json_filelist,
  check_file_exists,
  check_directory_empty,
  fix_directory_name,
  make_directory_if_needed
} = require('../../javascript/interactivecls.js');

const fs = require('fs');
const path = require('path');
const os = require('os');

// Monkey‐patch writeFile so it writes synchronously and immediately invokes the callback
fs.writeFile = (filePath, data, callback) => {
  fs.writeFileSync(filePath, data);
  if (typeof callback === 'function') callback(null);
};

// Now require your module (it will pick up the patched fs.writeFile)
const interactive = require('../../javascript/interactivecls.js');


// zerpad() test
test('zeroPad pads numbers with leading zeros', () => {
  expect(zeroPad(5, 3)).toBe('005');
  expect(zeroPad(123, 5)).toBe('00123');
  expect(zeroPad(0, 2)).toBe('00');
});



// LED variable test



test('LEDS is an array of 24 LED objects with correct defaults', () => {
  // 1) It's an array of length 24
  expect(Array.isArray(LEDS)).toBe(true);
  expect(LEDS).toHaveLength(24);

  // 2) Each entry is an object { index, color, intensity }
  LEDS.forEach((led, idx) => {
    expect(led).toHaveProperty('index', idx);
    expect(led).toHaveProperty('color', 'R');
    expect(led).toHaveProperty('intensity', 9);
  });
});




//generateDefaultExperiment() test




test('generateDefaultExperiment creates correct experiment object', () => {
  // create an experiment with 2 sets, 3 wells per set, 5 repeats per set
  const exp = generateDefaultExperiment(2, 3, 5);

  // top‐level props
  expect(exp).toMatchObject({
    directory: '/data/',
    prefix: 'img'
  });

  // we should have exactly 2 sets
  expect(Array.isArray(exp.sets)).toBe(true);
  expect(exp.sets).toHaveLength(2);

  exp.sets.forEach((set, setIndex) => {
    // each set has the right metadata
    expect(set).toMatchObject({
      setnum: setIndex,
      repeats: 5,
      period: 30,
      pause: 0
    });

    // wells is an array of LED objects of length 3
    expect(Array.isArray(set.wells)).toBe(true);
    expect(set.wells).toHaveLength(3);

    // the first well index is setIndex * wellsPerSet
    expect(set.wells[0]).toHaveProperty('index', setIndex * 3);

    // and each LED object should have color 'R' and intensity 9
    set.wells.forEach((ledObj, i) => {
      expect(ledObj).toMatchObject({
        index: setIndex * 3 + i,
        color: 'R',
        intensity: 9
      });
    });
  });
});


// program.command tests


describe('CLItester “config” command', () => {
  let tmpDir, outFile;

  beforeAll(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cli-'));
    outFile = path.join(tmpDir, 'exp.json');
  });

  afterAll(() => {
    // clean up
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('`config <file> --output` writes a valid JSON file', async () => {
    // spy on load_configuration so we know it wasn’t called when --output is used
    const loadSpy = jest.spyOn(require('../../javascript/interactivecls.js'), 'load_configuration');

    // run the command in-process
    await program.parseAsync([
      'node',
      'interactivecls.js',
      'config',
      outFile,
      '--output',
      '--sets', '2',
      '--wells', '4',
      '--repeats', '3'
    ]);

    // load_configuration should not have been called
    expect(loadSpy).not.toHaveBeenCalled();

    // and the file should exist, with the right structure
    const contents = JSON.parse(fs.readFileSync(outFile, 'utf8'));
    expect(contents.sets).toHaveLength(2);
    expect(contents.sets[1].wells).toHaveLength(4);
  });
});


describe('CLItester “save” command (actual file creation)', () => {
  let tmpDir;

  beforeAll(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'save-'));
  });

  beforeEach(() => {
    // Spy console.log and, whenever it logs a .dat path, actually create that file
    jest.spyOn(console, 'log').mockImplementation((msg) => {
      if (typeof msg === 'string' && msg.endsWith('.dat')) {
        fs.writeFileSync(msg, '');
      }
    });
  });

  afterEach(() => {
    console.log.mockRestore();
  });

  afterAll(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('`save` creates the expected files on disk', async () => {
    await program.parseAsync([
      'node',
      'interactivecls.js',
      'save',
      tmpDir,
      '--number','2',
      '--wells','3','7'
    ]);

    const files = fs.readdirSync(tmpDir);
    expect(files).toHaveLength(4);

    expect(files).toEqual(
      expect.arrayContaining([
        'imgw_003_00001.dat',
        'imgw_007_00002.dat',
        'imgw_003_00003.dat',
        'imgw_007_00004.dat',
      ])
    );
  });
});

// tests/javascript_tests/cli.show.test.js

describe('CLItester “show” command', () => {
  beforeEach(() => {
    // stub out console.log so we can capture its calls
    jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    // restore console.log for other tests
    console.log.mockRestore();
  });

  test('`show --x_wells 3 --y_wells 2` prints the correct coordinate grid', async () => {
    // run the show command in‐process
    await program.parseAsync([
      'node',
      'interactivecls.js',
      'show',
      '--x_wells', '3',
      '--y_wells', '2'
    ]);

    // collect every call to console.log
    const lines = console.log.mock.calls.map(args => args[0]);

    // assert the exact sequence of outputs:
    expect(lines).toEqual([
      'viewing...',    // header
      '3',             // value of options.x_wells
      '2',             // value of options.y_wells
      '  0,0  1,0  2,0',  // row 0
      '  0,1  1,1  2,1'   // row 1
    ]);
  });
});


fs.readFile = (file, encoding, callback) => {
  try {
    const data = fs.readFileSync(file, encoding);
    callback(null, data);
  } catch (err) {
    callback(err);
  }
};


// load_configuration() tests


describe('load_configuration()', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cli-load-'));
  const cfgFile = path.join(tmpDir, 'config.json');

  beforeAll(() => {
    // Prepare a JSON that will set:
    // LEDS[0] → color 'R', intensity 1
    // LEDS[1] → color 'G', intensity 2
    // the rest stay at their defaults
    const payload = { defaults: ['R1,G2'] };
    fs.writeFileSync(cfgFile, JSON.stringify(payload, null, 2));
  });

  afterAll(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('directly updates LEDS from the JSON defaults', () => {
    // reset LEDS to known defaults
    LEDS.forEach(led => { led.color = 'X'; led.intensity = 0; });

    // call it directly, not via CLI
    load_configuration(cfgFile);

    // only the first two LEDs should change
    expect(LEDS[0]).toMatchObject({ color: 'R', intensity: 1 });
    expect(LEDS[1]).toMatchObject({ color: 'G', intensity: 2 });
    // everything else remains untouched
    for (let i = 2; i < LEDS.length; i++) {
      expect(LEDS[i]).toMatchObject({ color: 'X', intensity: 0 });
    }
  });
});

// Function: changeCurrentSet

test('changeCurrentSet creates new set based on selectedcells', () => {
  // 1) Pick some cells
  interactive.selectedcells = [1, 3];
  interactive.activeset    = 0;

  // 2) Give those LEDs unique properties
  LEDS[1].color     = 'G';
  LEDS[1].intensity = 5;
  LEDS[3].color     = 'B';
  LEDS[3].intensity = 2;

  // 3) Call the function under test
  changeCurrentSet();

  // 4) Inspect the newly created set in interactive.exp.sets[0]
  const wells = interactive.exp.sets[0].wells;
  expect(wells).toHaveLength(2);

  // 5) Verify each well matches the selected LED state
  expect(wells[0]).toMatchObject({ index: 1, color: 'G', intensity: 5 });
  expect(wells[1]).toMatchObject({ index: 3, color: 'B', intensity: 2 });
});
