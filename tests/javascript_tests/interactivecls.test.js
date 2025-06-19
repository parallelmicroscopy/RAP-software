// At the *very* top of the test file:
jest.mock('commander', () => {
  // A minimal fake Commander.Program
  class FakeProg {
    version()   { return this; }
    description(){ return this; }
    option()    { return this; }
    command()   { return this; }
    action()    { return this; }
    parseAsync(){ return Promise.resolve(); }
  }
  const program = new FakeProg();
  return { program, Command: FakeProg };
});

const {
  program,
  exp,
  experiment,
  selectedcells,
  activeset,
  load_configuration,
  LED,
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

const rewire = require('rewire');
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
describe('changeCurrentSet()', () => {
  beforeEach(() => jest.resetModules());

  it('initializes a new set when none exists', () => {
    const interactive = require('../../javascript/interactivecls.js');
    const { exp, LEDS, LED, selectedcells, changeCurrentSet } = interactive;

    // Simulate selecting wells 2 and 5 with custom settings
    selectedcells.push(2, 5);
    LEDS[2].color = 'G'; LEDS[2].intensity = 3;
    LEDS[5].color = 'B'; LEDS[5].intensity = 7;

    // Invoke the function under test
    changeCurrentSet();

    const s = exp.sets[0];
    expect(s).toBeDefined();
    expect(s.setnum).toBe(0);
    expect(s.repeats).toBe(10);
    expect(s.wells).toHaveLength(2);
    expect(s.wells[0]).toEqual(expect.objectContaining({ index: 2, color: 'G', intensity: 3 }));
    expect(s.wells[1]).toEqual(expect.objectContaining({ index: 5, color: 'B', intensity: 7 }));
  });

  it('overwrites an existing set without changing repeats', () => {
    const interactive = require('../../javascript/interactivecls.js');
    const { exp, LEDS, LED, selectedcells, changeCurrentSet } = interactive;

    // Pre-populate an existing set at index 0
    exp.sets[0] = { setnum: 0, repeats: 4, wells: [ new LED(0, 'R', 1) ] };

    // Simulate selecting new wells 1 and 2
    selectedcells.push(1, 2);
    LEDS[1].color = 'Y'; LEDS[1].intensity = 5;
    LEDS[2].color = 'P'; LEDS[2].intensity = 8;

    // Invoke the function under test
    changeCurrentSet();

    const s = exp.sets[0];
    expect(s.setnum).toBe(0);
    expect(s.repeats).toBe(4);  // unchanged
    expect(s.wells).toHaveLength(2);
    expect(s.wells).toEqual(expect.arrayContaining([
      expect.objectContaining({ index: 1, color: 'Y', intensity: 5 }),
      expect.objectContaining({ index: 2, color: 'P', intensity: 8 })
    ]));
  });
});





describe('copySetToTable()', () => {
  let interactive, exp, LEDS, LED, copySetToTable, modulePath;

  beforeAll(() => {
    modulePath = require.resolve(
      path.join(__dirname, '../../javascript/interactivecls.js')
    );
  });

  beforeEach(() => {
    jest.resetModules();
    interactive    = rewire(modulePath);

    exp            = interactive.__get__('exp');
    LEDS           = interactive.__get__('LEDS');
    LED            = interactive.__get__('LED');
    copySetToTable = interactive.__get__('copySetToTable');
  });

  it('clears selectedcells when no active set exists', () => {
    let selectedcells = interactive.__get__('selectedcells');
    selectedcells.push(1, 2, 3);
    expect(selectedcells).toHaveLength(3);

    copySetToTable();

    selectedcells = interactive.__get__('selectedcells');
    expect(selectedcells).toHaveLength(0);
  });


});

describe('generateLEDList()', () => {
  it('returns an array of LED instances with correct indices, default color R and intensity 9', () => {
    const start = 0;
    const end = 3;
    const list = generateLEDList(start, end);
    // Should be an array of length end - start
    expect(Array.isArray(list)).toBe(true);
    expect(list).toHaveLength(end - start);

    // Each element should be an LED instance with proper properties
    list.forEach((led, i) => {
      expect(led).toBeInstanceOf(LED);
      expect(led).toMatchObject({ index: start + i, color: 'R', intensity: 9 });
    });
  });

  it('returns an empty array when start and end are equal', () => {
    const list = generateLEDList(5, 5);
    expect(Array.isArray(list)).toBe(true);
    expect(list).toHaveLength(0);
  });

  it('handles non-zero start correctly for arbitrary ranges', () => {
    const start = 22;
    const end = 24;
    const list = generateLEDList(start, end);
    expect(list).toHaveLength(2);
    expect(list[0]).toMatchObject({ index: 22, color: 'R', intensity: 9 });
    expect(list[1]).toMatchObject({ index: 23, color: 'R', intensity: 9 });
  });
});

describe('assignletter()', () => {
  it('returns letters a–z for indices 0 through 25', () => {
    for (let i = 0; i < 26; i++) {
      const expected = String.fromCharCode(97 + i); // 'a' has char code 97
      expect(assignletter(i)).toBe(expected);
    }
  });

  it('returns "*" for out-of-range indices', () => {
    expect(assignletter(26)).toBe('*');
    expect(assignletter(100)).toBe('*');
  });
});

