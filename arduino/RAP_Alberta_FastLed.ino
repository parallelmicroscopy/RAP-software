 #include <FastLED.h>
// Because conditional #includes don't work w/Arduino sketches...
#include <SPI.h>         // COMMENT OUT THIS LINE FOR GEMMA OR TRINKET
//#include <avr/power.h> // ENABLE THIS LINE FOR GEMMA OR TRINKET

#define NUMPIXELS 24 // Number of LEDs in strip

// Here's how to control the LEDs from any two pins:
#define DATAPIN    13
#define CLOCKPIN   7
#define TRIGGER    10
//Adafruit_DotStar strip(NUMPIXELS, DATAPIN, CLOCKPIN, DOTSTAR_RBG);
// The last parameter is optional -- this is the color data order of the
// DotStar strip, which has changed over time in different production runs.
// Your code just uses R,G,B colors, the library then reassigns as needed.
// Default is DOTSTAR_BRG, so change this if you have an earlier strip.

// Hardware SPI is a little faster, but must be wired to specific pins
// (Arduino Uno = pin 11 for data, 13 for clock, other boards are different).
//Adafruit_DotStar strip(NUMPIXELS, DOTSTAR_BRG);


int led_positions[24];
uint32_t  led_colors[24];
int led_intensities[24];
int user_itime=1000;
//0x000000
uint32_t reds[7]={0x070000,0x0F0000,0x1F0000,0x3F0000,0x7F0000,0xFF0000,0xFF0000};
uint32_t greens[7]={0x000700,0x000F00,0x001F00,0x003F00,0x007F00,0x00FF00,0x00FF00};
uint32_t blues[7]={0x000007,0x00000F,0x00001F,0x00003F,0x00007F,0x0000FF,0x0000FF};
CRGB leds[NUMPIXELS] = {0}; 

void setup() {
  FastLED.addLeds<APA102,   DATAPIN, CLOCKPIN, RGB>(leds, NUMPIXELS);

  pinMode(TRIGGER,OUTPUT);
  //strip.begin(); // Initialize pins for output
  for (int i=0;i<NUMPIXELS;i++) {
  //  strip.setPixelColor(i,0);
   led_positions[i]=-1;
  }
  
  //strip.show();  // Turn all LEDs off ASAP
  Serial.setTimeout(80);
  Serial.begin(9600);
}



// Runs 10 LEDs at a time along strip, cycling through red, green and blue.
// This requires about 200 mA for all the 'on' pixels + 1 mA per 'off' pixel.

int      head  = 24, tail = -1; // Index of first 'on' and 'off' pixels
uint32_t jcolor =  0x00FF00;  // 'On' color (starts red)
uint32_t kcolor = 0x0000FF;
uint32_t lcolor = 0x000000;
int rgb=0;
int count=0;
int j=0;
int k=4;
int allon=0;
int ta=78;
int ha=12;
int t=0;
String inString="";
int wellnumber=0;
int C;
int cycle24=0;

String strs[4];
int StringCount = 0;


int number_of_users=24;
uint32_t ledcolor;
int ledintensity;
int ledposition;
int currentindex=0;
long user_delay=50;
int uselow=0;


/*
Trigger in vimba
1) Trigger FrameStart
   TriggerMode On
   TriggerSource Line0
   TriggerActivation RisingEdge
   TriggerDelay 0
2) Trigger ExposureActive
   TriggerMode On
   TriggerSource Line0
   TriggerActivation LevelHigh

Acquisition Mode continuous
ExposureMode TriggerControlled.
*/
void loop() {
   int reset=1;
   for (int u=0;u<number_of_users;u++){
    ledposition=led_positions[u];
    ledcolor=led_colors[u];
    ledintensity=led_intensities[u];
    
    //if (uselow==1) ledintensity=int(ledintensity/4);
    if ((ledposition>-1)&&(ledposition<24)){
     if (reset==1) for (int i=0;i<NUMPIXELS;i++) leds[i]=0;
     leds[ledposition]=ledcolor;
     if (ledintensity>0){
     FastLED.show();
     
     digitalWrite(TRIGGER, HIGH);  
     delayMicroseconds(ledintensity);
     digitalWrite(TRIGGER,LOW);  
     delay(user_delay);
     reset=1;
     }else reset=0;
    }
   }
   
}



int split(String str){
StringCount=0;
while (str.length() > 0)
  {
    int index = str.indexOf(',');
    if (index == -1) // No space found
    {
      strs[StringCount++] = str;
      return StringCount;
      }
    else
    {
      strs[StringCount++] = str.substring(0, index);
      str = str.substring(index+1);
    }
  }

 return StringCount;
 
}

int parse_integer(){
   while (Serial.available()){
    char ic=(char)Serial.read();
    if (isDigit(ic)){
     inString+=(char)ic;
   }
   if (ic=='\n'){
    wellnumber=inString.toInt()-1;
    if ((wellnumber>-1) && (wellnumber< NUMPIXELS))  j=wellnumber;
    inString="";
   }
   }
   return wellnumber;
}

void resetLEDs(){
  for (int u=0;u<24;u++){
    led_positions[u]=-1;
    led_intensities[u]=99;
  }
}

void serialEvent(){
 
  while (Serial.available()){
    char ic=(char)Serial.read();
    //the following is for debugging or manual operatiion through serial monitor
    if (ic=='b') {allon=0; j=j-1; if (j==-1) j= NUMPIXELS-1;}
    if (ic=='f') {allon=0; j=j+1; if (j>=NUMPIXELS) j=0;}
    if (ic=='a') allon=1;
    if (ic=='c') rgb+=1;
    if ((ic=='h')) {cycle24=1; return;}
    if ((ic=='H')) cycle24=0;
    if (rgb%3==0) jcolor=0x0000FF;
     else if (rgb%3==1) jcolor=0xFF0000;
     else jcolor=0x00FF00;

   //str="user="+cellID+",well="+n+",col="+setcolornumber+",i="+bv.value;
    if (ic=='d'){
      String str= Serial.readString();
      user_delay=str.toInt();
      Serial.flush();
      return;
    }
    if (ic=='r'){
      //reset
      resetLEDs();
      Serial.flush();
      return;
    
    }
    if (ic=='m'){
      String str=Serial.readString();
      user_itime=str.toInt();
      Serial.flush();
      return;
    }
    if (ic=='l'){
     if (uselow==1) {
       uselow=0;
       for (int k=0;k<24;k++)led_positions[k]=-1;
     }
     else{
     uselow=1;
     for (int k=0;k<24;k++){
      led_positions[k]=k;
      led_colors[k]=0xFF0000;
      
      led_intensities[k]=99;
      if ((k>2)&&(k<5)) led_intensities[k]=50;
     }
     }
    }
    if (ic=='n'){
      String str= Serial.readString();
      number_of_users=str.toInt();
      Serial.flush();
      return;
    }
    if (ic=='p'){
     String str =  Serial.readString();
     split(str);
     currentindex=strs[0].toInt();
     ledposition=strs[1].toInt()-1;
     ledcolor=strs[2].toInt();
     //ledintensity=int((strs[3].toInt()/100.0)*6);
     ledintensity=strs[3].toInt();
     
     if ((currentindex>-1)&&(currentindex<24)){
      led_positions[currentindex]=ledposition;
      if (ledcolor==0) led_colors[currentindex]=0x00FF00;
      /*
      if (ledcolor==1) led_colors[currentindex]=reds[ledintensity];
      if (ledcolor==2) led_colors[currentindex]=greens[ledintensity];
      if (ledcolor==3) led_colors[currentindex]=blues[ledintensity];
      */
      
      if (ledcolor==1) led_colors[currentindex]=0xFF0000;
      if (ledcolor==2) led_colors[currentindex]=0x00FF00;
      if (ledcolor==3) led_colors[currentindex]=0x0000FF;
      
      led_intensities[currentindex]=ledintensity*20;
     }
     Serial.flush();
     return;
    }

    Serial.flush();
   
  }
}
