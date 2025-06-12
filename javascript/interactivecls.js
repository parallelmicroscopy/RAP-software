const { program } = require('commander');
const { Input } = require('enquirer');
const path = require('path');
const { Prompt } =require('enquirer');
const { prompt } = require('enquirer');
const { Confirm } = require('enquirer');

//const { Select } =require('enquirer');
var readline = require('readline');
const prompts = require('prompts');
var Table = require('cli-table3'); //for ASCII table
var clc = require("cli-color"); //for colors
const { spawn } = require('child_process'); //lets you launch the Python script as a subprocess and pipe data to/from it
const nexline=require('nexline'); //can convert a stream to an async iterator
const fs = require('node:fs');
const { AutoComplete } = require('enquirer');
const Store = require('data-store'); //provides a simple JSON-backed key/value store on disk
const { SerialPort } = require('serialport');
const YAML = require('yaml')
//const fileDialog = require('file-dialog')
const { Snippet } = require('enquirer');





var defaultJSONdirectory=".";
var defaultDataDirectory=".";

var arduino_connected=false;

var python_user_command="<jmessage>";

const zeroPad = (num, places) => String(num).padStart(places, '0') //so that all your strings of numbers can be same size

class MyInput extends Input{ //allows you to scroll through a history of commands
  up(){
    return this.completion('prev');
    this.render();

  }
  down(){
    return this.completion('next');
    this.render();
  }
}

class LED{ //LED object
  constructor(index,color,intensity){
    this.color=color;
    this.index=index;
    this.intensity=intensity;
  }
}

//LEDS is used by drawtable. Its used to represent the entire LED array.
var LEDS=[];
for (i=0;i<24;i++) LEDS.push(new LED(i,"R",9));


class experiment{ //for holding experiment configurations
  directory="";
  prefix="";
  sets=[];
}

function generateDefaultExperiment(numberofsets,wellsperset,repeatsperset){ //creates experiment objects with sets if configurations
  var exp=new experiment();
  exp.directory="/data/";
  exp.prefix="img";
  exp.sets=[];
  for (k=0;k<numberofsets;k++){
    var subobj={};
    subobj["setnum"]=k;
    subobj["repeats"]=repeatsperset;
    subobj["period"]=30;
    subobj["pause"]=0;
    subobj["wells"]=generateLEDList(k*wellsperset,k*wellsperset+ wellsperset);
    exp.sets.push(subobj);
   }
   return exp;
  }

//onfiguring your Commander program’s metadata
program
  .name('CLItester')
  .description('a CLI framework tester')
  .version('1.0.0')


program.command('config') //defines config subcommand for changing configurations
  .description('read/write configuration file')
  .argument('<string>','complete path to file')
  .option('-o,--output','writes a config file with default values')
  .option('-w,--wells <int>','number of wells to write (default 24)',24)
  .option('-s,--sets <int>', 'number of sets (default 1), each set as w wells',1)
  .option('-r,--repeats <int>', 'number of repeats per set (default 1)',1)
  .option('-d, --duration <int>','period in milliseconds(LED switch time, default 30)',30)
  .action((str,options)  => {
    if (options.output){
      jsob=generateDefaultExperiment(Number(options.sets),Number(options.wells),Number(options.repeats),Number(options.duration));
      lliststr=JSON.stringify(jsob,null,2);
      fs.writeFile(str,lliststr,err=>{
        if (err) {
          console.error(err);
        } else {
          console.log("file written");
        }
      });
    }else{
      load_configuration(str);

    return;
  }
  });

program.command('save') //allows user to store files with customized name
  .description('store images to local disk')
  .argument('<string>','complete path to the directory')
  .option('-p, --prefix <string>','filename prefix','img')
  .option('-n, --number <int>', 'number of frames to store',10)
  .option('-s, --start  <int>', 'starting frame (default 1)',1)
  .option('-w, --wells <int...>','wells e.g. 3 7 12 24','1')
  .action((str,options) => {
    console.log('saving...');
    console.log('wells length = '+options.wells.length);
    for (i=0;i<options.number*options.wells.length;i++) {
      var wstr="w_"+zeroPad(options.wells[i%options.wells.length],3)+"_";
      fp=str+path.sep+options.prefix+wstr+zeroPad(options.start+i,5)+".dat";
      console.log(fp);
    }
  });

program.command('show') //prints out a simple x×y grid of coordinate placeholders
  .description('show live images on the screen')
  .option('-xi, --x_wells <int>','the number of frames in the x direction',1)
  .option('-yi, --y_wells <int>', 'the number of frames in the y direction',1)
  .option('-xd, --xdim <int>', 'image width (xdimension)',-1)
  .option('-yd, --ydim <int>', 'image height (ydimension)',-1)
  .option('-xo, --xoffset <int>','x offset (on screen)',1)
  .option('-yo, --yoffset <int>','y offset (on screen)',1)
  .option('-w, --wells <int...>','wells e.g. 3 7 12 24')
  .action((options)=>{
    console.log('viewing...');
    console.log(options.x_wells);
    console.log(options.y_wells);
    for (y=0;y<options.y_wells;y++){
      str="";
      for (x=0;x<options.x_wells;x++){
        str+="  "+x+","+y;
      }
      console.log(str);
    }
  });

//lets commander read arguments
program.parse();
const options = program.opts();


function load_configuration(configfilename){ //reads a JSON file containing your experiment or LED defaults
  fs.readFile(configfilename, 'utf8', (err, data) => {
    if (err) {
      console.error(err);
      return;
    }
    exp = JSON.parse(data);
    try{
       for (i=0;i<exp.defaults.length;i++){
        row=exp.defaults[i].split(',');
        for (j=0;j<row.length;j++){
          lednum=i*row.length+j;
          LEDS[lednum].color=row[j][0];
          LEDS[lednum].intensity=Number(row[j][1]);
        }
       }
    }
    catch(error){
      console.error("potential error reading json file (for 'defaults' setting): "+error);

    }
  });
}

var exp=new experiment();
var activeset=0; //index of current set
var activecell=0;//index of current cell
var selectedcells=[];
var respondtokeys=0; //controls whether your keypress listener should actually modify

function changeCurrentSet(){ //creates new set containing the ones you have selected
  tmp=[];
  for (let i = 0; i < selectedcells.length; i++) {
    tv=LEDS[selectedcells[i]];
    tmp.push(new LED(tv.index,tv.color,tv.intensity));
  }
  if (typeof exp.sets[activeset] == "undefined"){
    exp.sets[activeset]={};
    exp.sets[activeset].setnum=activeset;
    exp.sets[activeset].repeats=10;
  }
  exp.sets[activeset].wells=tmp;
}

function copySetToTable(){ //takes activeset and copies it into selected cells
  if (typeof exp.sets[activeset]!="undefined"){
    selectedcells=[];
    for (i=0;i<exp.sets[activeset].wells.length;i++){
      well=exp.sets[activeset].wells[i];
      selectedcells.push(well.index);
      try{
      LEDS[well.index].color=well.color;
      }catch{
        console.log("****                           error: well index = "+well.index+ " i = "+i);
      }
    }
  } else{
    selectedcells=[];
  }
}



function generateLEDList(startLED,endLED){ //helper function that generates list of default LED's
  var res=[]
  for (i=startLED;i<endLED;i++){
    tmp=new LED(i,"R",9);
    res.push(tmp);
  }
  return res;
}

function assignletter(i){ //allows any non-negative index
  lcase=['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z'];
  if (i<lcase.length) return lcase[i];
  else return ('*');
}

function selectedindex(i){ //returns index of desired cell
  for (var k=0;k<selectedcells.length;k++){
    if (selectedcells[k]==i) return k;
  }
  return -1;
}

function renderTable(xdim,ydim){ //draws grid of selected cells in terminal
  var table=new Table({
      style: { 'padding-left': 0, 'padding-right': 0, head: [], border: [] },
     });
     var num=0;
     lcase="abcdefghijklmnopqrstuvwxyz";
     blch=clc.cyan('\u25cf');
     rdch=clc.red('\u25cf');
     grch=clc.green('\u25cf');
     nlch='\u25CB';
     var selected=clc.underline;
     for (var y=0;y<ydim;y++){
      var row=[];
      for (var x=0;x<xdim;x++){
        var isselected=selectedcells.includes(num);
        var letter=num;
        var led=LEDS[num];
        var ch=nlch;
        if (isselected || num==activecell){
          ch=rdch;
          if (led.color=='G') ch=grch; if (led.color=='B') ch=blch;
        }
        sch=" ";
        if (isselected) {
          ml=assignletter(selectedindex(num));
          sch=clc.cyan(ml);
          if (led.intensity==0) sch=clc.white(ml);
        }
        var ledstring=led.index;
        if (num==activecell) ledstring=selected(led.index);
        str=ledstring+sch+"\n"+led.color+ch+","+led.intensity;
        row.push(str);
        num++;
      }
      table.push(row);
    }

  console.log(table.toString());
}

class waitForEnter extends Prompt {//custom prompt class
  constructor(options = {}) {
    super(options);
    this.cursorHide();
  }
  render() {
  }
}

const ctable = new waitForEnter({ //subclass of Prompt, silently waits for user to enter something
  message: ''
});

function live(listen){ //puts node.js process into live mode and allows you to navigate and edit the grid by talking to arduino

 readline.emitKeypressEvents(process.stdin);
 if (process.stdin.isTTY)
    process.stdin.setRawMode(true);

 process.stdin.on('keypress', (chunk, key) => {
  if (respondtokeys==1){
  if (key){
  if ((key.name=='x')||(key.name=='space')){
    if (selectedcells.includes(activecell)){
      const i=selectedcells.indexOf(activecell);
      selectedcells.splice(i,1);
    }
    else selectedcells.push(activecell);
  }
  if ((key.name=='a')||(key.name=='left')) activecell--;
  if ((key.name=='d')||(key.name=='right')) activecell++;
  if ((key.name=='w')||(key.name=='up')) activecell-=6;
  if ((key.name=='s')||(key.name=='down')) activecell+=6;
  if (key.name=='c') {
    var nc;
    var c=LEDS[activecell].color;
    if (c=='R') nc='G';
    else if (c=='G') nc='B';
    else if (c=='B') nc='R';
    LEDS[activecell].color=nc;
  }
  if (key.name=='i'){
    var intensity=LEDS[activecell].intensity;
    intensity-=1;
    if (intensity<1) intensity=9;
    LEDS[activecell].intensity=intensity;
  }
  if (key.name=='m'){
    if (LEDS[activecell].intensity==0) LEDS[activecell].intensity=9;
    else  LEDS[activecell].intensity=0;
  }
  if (key.name=='f'){
    changeCurrentSet();
    activeset--;
    if (activeset<0) activeset=0;
    copySetToTable();
  }
  if (key.name=='g'){
    changeCurrentSet();
    activeset++;
    copySetToTable();
  }
  if (activecell<0) activecell+=24;
  if (activecell>=24) activecell-=24;
  if (key.name == 'q') {
     respondtokeys=0;
     console.log("hit enter to return to option list.");

  }
  }
   drawLiveInputTable();

  send_to_arduino(led_to_arduino_string(activecell,0));
  }
  });
}


function led_to_arduino_string(lednumber,position){ //builds the exact serial‐command string that you send to your Arduino
  var colorcode=1;
   if (LEDS[lednumber].color=='B') colorcode=2;
   if (LEDS[lednumber].color=='G') colorcode=3;
   var str="p"+position+","+(lednumber)+","+colorcode+","+LEDS[lednumber].intensity;
   return str;

}

/*
function qtest(){
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    });
    console.log('in qtest');
    rl.question(`What's your name?`, name => {
      console.log(`Hi ${name}!`);
      rl.close();
      nextOption(cli_options);
    });
}
*/




function writeStatus(){
  console.log("selected wells: "+ selectedcells);
  console.log("viewed well: ", activecell);
}

var table_drawn=false;
function drawLiveInputTable(){ //allows navigation/editing without having to reprint the grid
  //console.log(clc.erase.screen);
  //copySetToTable();
  if (table_drawn) console.log(clc.move(0, -22));
  console.log(clc.underline.cyan("Usage:"));
  str=`  <wasd> or arrow keys to navigate
  <x> or spacebar to add/remove a well
  <c> change color <m> multi
  <i> change intensity
  <enter> when done.
  <f,g> prior set, next set.
  current set = ${activeset}`;
  console.log(str);
  renderTable(6,4);
  table_drawn=true;

}


const chooseset={ //question definition
  type: 'number',
  name: 'value',
  message: 'Choose active set #',
  validate: value=> value > 24 ? 'between 1 and 24': true
};

const confirm={ //prompt to wait for input

    type: 'invisible',
    name: 'value',
    message: "",
    initial: true

}



const arduino_command={ //prompt to ask for arduino command
  type: 'input',
  name: 'value',
  message: 'enter arduino command (q to quit)',
};

//allows you to select a number of LED's
const a24=Array(24)
for (i=1;i<25;i++) a24[i-1]=i;
var long_list={
  type: 'multiselect',
  name: 'leds',
  message: 'led list',
  choices: a24,
}


 /*
 The user enters a directory name. The program should
  1) accept it if exists and is empty,
  2) create it not.
 if the directory now exists and is empty, then
  1) change exp savedirectory in the json exp file
  2) copy the file to the directory
  3) if the python program is open: send a change directory command to that program.
      this would be: path.resolve(mydir)
 else:
  let the user know the operation failed.

 */
function fix_directory_name(mydir_uncorrected){ //convert any OS specific paths to a Mac compatible path
  mydir = mydir_uncorrected.replaceAll(path.sep, "/");
  return mydir;
}
//returns 1 if the directory has been created or exists and is impty, 0 or -1 otherwise.
function make_directory_if_needed(mydir){
  var success=0
  if (check_file_exists(mydir)==0){
    try {
        fs.mkdir(mydir);
        success=1

    } catch (err) {
      console.error(err);
      success=0
    }
  } else {
  //directory exists - is it empty?
    success=check_directory_empty(mydir);
  }
  return success
}

//check if a directory exists - 1 if true, 0 if not
function check_file_exists(mydir){
  var file_exists=-1;

 if (fs.existsSync(mydir)) {
    console.log(`The file ${mydir} exists.`);
    file_exists=1;
  } else {
    console.log(`The file ${mydir} does not exist.`);
    file_exists=0;
  }

  console.log("\n cfe returning ",file_exists);
  return file_exists;
}


//check if a directory is impty 0 = not empty, 1 = empty, -1 some error
function check_directory_empty(mydir){
  var directory_empty=0
 fs.readdir(mydir, function(err, files) {
  if (err) {
       directory_empty=-1
   } else {
     if (!files.length) {
         // directory appears to be empty
         directory_empty=1
     }
  }
 });
 return directory_empty;
}

//returns list of all files and folders in current directory
function getfilelist(){
  return fs.readdirSync(defaultJSONdirectory);
}

// returns list of JSON files in the current directory
function get_json_filelist(){
   var arr=getfilelist();
   return arr.filter(isJSONfile);
}


var currentdirectorylisting=getfilelist();
//console.log(array.filter(isPrime));

//checks if a file is  JSON file
function isJSONfile(filename){
  var retval=false;
  if (filename.toLowerCase().includes('json')) retval=true;
  if (filename.toLowerCase().includes('jsn')) retval=true;
  return retval;
}

//checks if something is a directory
function isDirectory(filename){
  if (check_file_exists(filename)==1)
   return fs.lstatSync(filename).isDirectory();
  return false;
}

//lets user fill in fields from terminal
function fillJSONglobals(){
  const instructions=`
  1) 'directory' should be a empty folder in path 'directory_root'
      or a folder name that doesn't exist.
      *If the folder doesn't exist, set create_if_needed to 'y'*
  2) 'prefix' is the image prefix e.g 'img' for img00001.tif, img0002.tif etc
  3) saveN = number of images to save (e.g. 100) or -1 for save until stopped
  4) 'repeats' = number of loops (of all sets) before stopping the experiment
  `
  const formprompt = new Snippet({
    name: 'username',
    message: instructions,
    required: true,
    fields: [
      {
        name: 'directory',
        message: 'folder name'
      },
      {
        name: 'directory_path',
        initial: '/users/gilbub/documents/',
        validate(value, state, item, index) {
          if (item && item.name === 'directoryPath' && !isDirectory(value)) {
            return formprompt.styles.danger('directory path not valid...');
          }
          return true;
        }
      },
      {
        name: 'overwrite',
        initial: 'n'
      },
      { name: 'create',
        initial: 'n'
      }
    ],
    template: `{
    "directory_root": "\${directory_path}",
    "directory": "\${directory}",
    "allow_overwrite": "\${overwrite}",
    "create_if_needed": "\${create}",
    "prefix": "\${prefix}",
    "saveN" : "\${saveN}",
    "repeats": "\${repeats}"
  }
  `
  });

  formprompt.run()
    .then(answer => {console.log('Answer:', answer.result);processJSONglobals(answer.result);})
    .catch(console.error);
}

//again allows user to complete a form in terminal
function fillJSONset(){
  const instructions=`
  1) 'setnum' = the current set to edit
  2) 'repeats' = the number of times the sequence in that set repeats
  3) 'period'  = the period in milliseconds between each element in the sequence
  4) 'pause'   = the delay between the current set and the next one in milliseconds
  `
  const formprompt = new Snippet({
    name: 'username',
    message: instructions,
    required: true,
    fields: [
      {
        name: 'setnum',
        message: 'set number'
      },
      {
        name: 'repeats',
        initial: '10',
      },
      {
        name: 'period',
        initial: '30'
      },
      { name: 'pause',
        initial: '1000'
      }
    ],
    template: `{
    "setnum": "\${setnum}",
    "repeats": "\${repeats}",
    "period": "\${period}",
    "pause": "\${pause}"
  }
  `
  });

  formprompt.run()
    .then(answer => {console.log('Answer:', answer.result);processJSONset(answer.result);})
    .catch(console.error);
}


//parses completed form and processes answers
function processJSONglobals(ans){
  exp_details = JSON.parse(ans);
  exp.directory=exp_details.directory_root+exp_details.directory;
  exp.prefix=exp_details.prefix;
  exp.repeats=exp_details.repeats;
  nextOption(config_options);
}

//parses completed form and processes answers
function processJSONset(ans){
  exp_details = JSON.parse(ans);
  set_n=exp_details.setnum;
  exp.sets[set_n].repeats=exp_details.repeats;
  exp.sets[set_n].period=exp_details.period;
  exp.sets[set_n].pause = exp_details.pause;
  nextOption(config_options);
}


//Uses autocomplete from ENQUIRER to give the user a list of available JSON files
function getJSONFileName(){
      var fileprompt = new AutoComplete({
      name: 'myfile',
      message: 'pick a json file',

      choices: get_json_filelist()
     });

     fileprompt.run()
    .then(answer => {
      readJSONFile(answer);

    })
    .catch(error=>{console.log("error"); nextOption(config_options)});
}

//takes users choice and confirms they want to proceed
function readJSONFile(filename){
  tmp=[defaultJSONdirectory,filename]
  var fullpath=tmp.join('/');
  var yes_no_prompt = new Confirm({
    name: 'yes_no',
    message: 'Proceed?'
  });
  yes_no_prompt.run()
    .then(answer => {if (answer){
      load_configuration(fullpath);
      nextOption(config_options);
    } else {
      console.log("cancelled");
      nextOption(config_options);
    }
  })
    .catch(error=>{console.log(error);nextOption(config_options);});
}

//displays commands to user
const python_help_string=`
Python commands
(usually 'startpython', followed by <trigger,1>, then <startcamera>)
-------------------------------------------------------
startpython             : launch python (and initialize the camera)

commands sent to the python subprocess (enclosed with < >):
-----------------------------------------------------------
<trigger,1>             : setup camera for trigger run. Call this before <startcamera>.
<startcamera>           : starts the camera loop (call this after <trigger,1>)
<quit>                  : exit python (close cameras) (call startcamera first)
<startsave>             : start saving data in default save directory (call startcamera first)
<stopsave>              : stop saving data (call startsave first)
<gain,20>               : sets the gain to 20 (choose a value between 0 and 45).
<setdir,absolutepath>   : set the default save directory
`;
const arduino_help_string=`
Arduino low level commands:
----------------
 d# : delay (in ms) e.g.'d30'
 M : run current configuration (e.g. 'M', runs through sets of sequences e.g 'S0,5,10,30')
 m : live mode (set sequence manually e.g. 's0,5')
 H : pause, h : restart (e.g 'H' or 'h')

Sequence Control (for debugging):
--------------------------------
 N#: number of sequences e.g. 'N3'
 s#start,#end: manually run sequence of leds e.g. 's10,15'
 p#position,#led,#color(1-3),#intensity(1-99) e.g. 'p1,10,3,99'
 S#sequence,#start,#end,#number_of_iterates,delay e.g. 'S0,0,10,300,30'<enter>'S1,10,3,300,30'
 `;

//lets user send commands to the arduino and shows history
function run_arduino_command(){
  var arduino=new MyInput({
    message: "Arduino command(arrows:history, '-q':quit, '-h':help):",
    initial: 'p0,1,1,99',
    history: {
      store: new Store({ path: `arduino_history.json` }),
      autosave: true
    }
  });
   arduino.run()
      .then(answer=>{
        console.log('answer:',answer);
        if (answer=="-h"){console.log(arduino_help_string);run_arduino_command();}
        else
        if (answer!="-q") {send_to_arduino(answer); run_arduino_command();}
        else
        nextOption(cli_options);}
      )
      .catch(console.error);
}

//same as prev function but in python
function run_python_command(){
  var mypython=new MyInput({
    message: "Python command(arrows:history, '-q':quit, '-m' :messages, '-h':help):",
    initial: 'startpython',
    history: {
      store: new Store({ path: `python_history.json` }),
      autosave: true
    }
  });
   mypython.run()
      .then(answer=>{
        console.log('answer:',answer);
        if ((answer=="startpython")||(answer=="runpython")){ run_python(); run_python_command();}
        else
        if (answer=="-h"){console.log(python_help_string);run_python_command();}
        else
        if (answer=="-m"){console.log( python_text_out);run_python_command();}
        else
        if (answer!="-q") {send_python(answer); run_python_command();}

        else{

          nextOption(cli_options);
        }
      }
      )
      .catch(console.error);

}


//from Prompt library allows user to select configuration
const config_options={
  type: 'select',
  name: 'nextFunction',
  message: 'Config Options',
  choices: [
    { title: 'Save json configuration', value: 101 },
    { title: 'Load json configuration', value: 102},
    { title: 'Show json configuration', value: 103},
    { title: 'Change global config settings', value: 104},
    { title: 'Change set config settings', value: 109},
    { title: 'Edit json configuration', value: 108},
    { title: 'choose set', value: 105},
    { title: 'upload set', value: 106},
    { title: 'upload experiment', value:107},
    { title: 'main menu', value:1000}
  ],
};

//allows user to select which menu they want to go to
const cli_options={
    type: 'select',
    name: 'nextFunction',
    message: 'Main menu',

    choices: [
      { title: 'configuration menu', value: 100},
      { title: 'live mode', value: 1 },
      { title: 'python command', value:2  },
      { title: 'arduino command', value:3},
      { title: 'quit', value: 0 }
    ],
  };


//central menu router
async function nextOption(myquestion){
  var response = await prompts(myquestion);
  var rval=parseInt(response['nextFunction']);
  console.log("received "+rval);
  respondtokeys=0;

  switch(rval){
    case 0: //exit
      console.log("exit program");
      return 0;
      break;

    case 1000: //back to main menu
      nextOption(cli_options);
      break;

    case 100: //config menu
      nextOption(config_options);
      break;

    case 1: //live mode
        respondtokeys=1;
        send_to_arduino("d30");
        send_to_arduino("s0,1");
        copySetToTable(); //loads currently active set into UI
        drawLiveInputTable();
        response=await prompts(confirm); //wait for user to press enter
        respondtokeys=0;
        table_drawn=false;
        writeStatus();
        changeCurrentSet();
        nextOption(cli_options);
        break;

    case 2: //lets user control camera using python
        run_python_command();
        //run python keeps it in that mode until it receives -q
        break;

    case 3: //lets user conrtol camera using arduino
        run_arduino_command();
        //run arduino keeps it in that mode until it receives -q
        break;


    case 101: //saves JSON configuration
      console.log("saving configuration");
      lliststr=JSON.stringify(exp,null,2);
      fs.writeFile("currentconfig.json",lliststr,err=>{
        if (err) {
          console.error(err);
        } else {
          console.log("file written");
        }
      });
      nextOption(config_options);
      break;


    case 103:
        //show experiment configuration on screen
        console.log("showing...");
        console.dir(exp, {depth: null, colors: true});
        nextOption(config_options);
        respondtokeys=0;
        break;

    case 102: //choose JSON config directory then pick specific file
      var directory=defaultJSONdirectory;
      const prompt = new Input({
        message: 'Which config file (.json) directory?',
        initial: directory,
        //validate(value,state,item,index){if (fs.existsSync(value)) return(true); else return("not a directory")}
        validate(value,state,item,index){if (isDirectory(value)) return(true); else return("...not a directory")}
      });

      prompt.run()
      .then(answer =>
        {console.log('Answer:', answer);
          defaultJSONdirectory=answer;
          getJSONFileName();
        })
      .catch(console.log);
      //nextOption(config_options);


      break;

    case 104://edit global experiment settings
      //set the python save directory
      fillJSONglobals();
      /*
      var directory=defaultDataDirectory;
      const dirprompt = new Input({
        message: 'Which data directory?',
        initial: directory,
        //validate(value,state,item,index){if (fs.existsSync(value)) return(true); else return("not a directory")}
        validate(value,state,item,index){if (isDirectory(value)) return(true); else return("...not a directory")}
      });
      dirprompt.run()
         .then(answer =>{defaultDataDirectory=answer;console.log("default data directory = ",defaultDataDirectory); nextOption(config_options);})
         .catch(console.log);
      */
      break;
    case 109://edit specific set configs
      fillJSONset();
      break;
    case 105: //choose active set
      console.log('going to choose set');
      response=await prompts(chooseset);
      console.log('number recevieved=',response['value']);
      activeset=response['value'];
      if (activeset<0) activeset=0;
      //copySetToTable();
      nextOption(config_options);
      break;

    case 106: //lights up selected LED's
        upload_last_set_to_arduino();
        nextOption(config_options);
        break;

    case 107: //goes through exp.sets in order and uploads to arduino
        upload_exp_to_arduino();
        nextOption(config_options);
        break;

    case 108: //allows manual editing
      var editor = new Editor({
        type: 'editor',
        name: 'background',
        message: 'possibly useless?',
        currentText: 'some starter text',
        validate: function (text) {
          if (text.split('\n').length < 3) {
            return 'Must be at least 3 lines.';
          }
          return true;
        }
      });

      editor.run()
        .then(function(answers) {
          console.log(answers);
          nextOption(config_options);
        });
       break;


/*
    case 5:
      console.log('led listing');
      response=await prompts(long_list);
      console.log(response);
      nextOption(cli_options);
      break;
    case 6:
      run_python();
      nextOption(cli_options);
      break;

    case 8:
      send_python("<quit>");
      nextOption(cli_options);
      break;





    case 12:
        //yaml output
        var yamlstr=YAML.stringify(exp);
        console.log(yamlstr);
        nextOption(cli_options);
        break;

*/
    default: //back to main menu
      nextOption(cli_options);
  }

}

//uploads each set to arduino in order
async function upload_exp_to_arduino(){
  send_to_arduino("h");
  var beginval=0;
  var number_of_sets=0;
  console.log("number of sets ="+exp.sets.length);
  for (var i=0;i<exp.sets.length;i++){
    if (exp.sets[i].wells.length>0){
      activeset=i;
      number_of_sets+=1;
      copySetToTable();
      //set info:
      var setstr="S"+activeset+","+beginval+","+(beginval+selectedcells.length+","+exp.sets[activeset].repeats+",0");
      console.log(setstr);
      //beginval+=selectedcells.length;
      send_to_arduino(setstr);
      await sleep(50);
      for (var j=0;j<selectedcells.length;j++){
        var ledstring=led_to_arduino_string(selectedcells[j],beginval+j);
        console.log(ledstring);
        send_to_arduino(ledstring);
        await sleep(50);
       }
       beginval+=selectedcells.length;
       //sequence_number,start,end,number_of_iterates,delay
    }
  }
  send_to_arduino("N"+number_of_sets);
}

//uploads current set to the LED
async function upload_last_set_to_arduino(){
  send_to_arduino("h");
  for (var i=0;i<selectedcells.length;i++){

      send_to_arduino(led_to_arduino_string(selectedcells[i],i));
      await sleep(5);
  }
  send_to_arduino("s0,"+selectedcells.length);
}

//lets you pause to allow other things to process
function sleep(ms) {
	return new Promise((resolve) => {
	  setTimeout(resolve, ms);
	});
}

//sends a singular command to arduino
async function send_to_arduino(bstr){
  if (arduino_connected==false) return;
  var str="<"+bstr+">"
  port.write(str, (err)=>{
		if (err) throw err;
		//console.log(str);
		//console.log("write to port successful");
	  });
	port.flush();
}



//spawns python process
var python; //Node.js ChildProcess object running vimba_rap3.py
var reader;

var python_initialized=0
var show_output_from_python=1
var python_text_out=[]
async function run_python(){
  console.log("trying to run python vimba_rap3.py\n")
  const spawn = require("child_process").spawn;
  const pyFile = '../python/vimba_rap3.py';
  python = spawn("python3", [pyFile, {stdio:["pipe","pipe","inherit"]} ]);
  python.on(`spawn`, () => {
    //console.log(`[node:data:out] Sending initial data packet`);
    //since this doesn't say quit - python will ask for a frame
    python_initialized=1;
    send_python(python_user_command); //Sends an initial handshake
    });
     reader = nexline({
      input: python.stdout,
    })
    for await(const line of reader) {
      if (show_output_from_python==1){
       if (line.includes("py. ")){


        python_text_out.push('[from python] '+ line+'\n');

       }
      }
      //send_python(python_user_command);
    }

}


 /*
 the problem - if i get a frame, I have to emmediately ask for another. This means that there is a process that
 just a loop with no user input.
 There needs to be some continuously running process that responds 'ok' to every question
 while this process is going on, node js is blocked.

 node js can't respond each time because it is reading lines

 if use stdin/out to talk to python,
  send_python(getframe);
  const nl = nexline({input: python.stdout});
  while(true) {
    const line = await nl.next();
    console.log(line);
    if (line === null) break; // If all data is read, returns null
  }

  or have it run in its own loop.

 */

//send get command to python file
 async function python_get_frames(){
  python.stdin.write(`get\n`);
 }

//send python commands
async function send_python(str){

  if (python_initialized==1)
    python.stdin.write(str+"\n");

}

//start/stop streaming
async function start_camera_run(){
  send_python("startcamera");
}
async function stop_camera_run(){
  send_python("stopcamera");
}


var port;

  /*
  port = new SerialPort({
  path:"/dev/cu.usbmodem1101",
  baudRate: 9600
  });
  */
  //SerialPort.list().then(ports=>console.log(ports), err=>console.log(err))


//scans and connects to arduino
SerialPort.list().then(ports=>ConnectIfAttached(ports,"rduino"),err=>console.log(err));
function ConnectIfAttached(ports,findstr){
  arduino_connected=false;
  for (i=0;i<ports.length;i++){
    //console.log("port #"+i);
    //console.log(ports[i]);
    //console.log("---");
    devicename=ports[i].manufacturer;
    var devicepath=ports[i].path;
    if (devicename!=null){
    if (devicename.includes(findstr)) {
      //console.log("found an arduino");
      //console.log("manufacturer:")
      //console.log(ports[i].manufacturer);
      port=new SerialPort({path: devicepath, baudRate: 9600});
      arduino_connected=true;
    }
    }

  }
  return false;
}


//listen to keypresses (live())
live();
nextOption(cli_options);

