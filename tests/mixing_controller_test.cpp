#include "../esphome/packages/mixing_controller.h"
#include <cassert>
#include <iostream>
using namespace virtual_climate;
struct Plant {
  MixingController control{MixingConfig{50}};
  ValveInput input{0, 35, 35, 35, 0, false, true, false, false, true, false, false};
  ValveOutput step(double seconds=5, bool fresh=true) {
    input.now += seconds;
    if (fresh) control.sample(input);
    auto output = control.tick(input);
    if (output.command) input.position = output.position;
    return output;
  }
  void advance(int seconds) { for(int i=0; i<seconds/5; ++i) step(); }
};
int main() {
  for (bool ufh : {false,true}) for (bool radiator : {false,true}) for (bool cooling : {false,true})
    assert(heat_relay(ufh,radiator,cooling)==(!cooling && (ufh||radiator)));
  { // Pump-off closes even with manual enabled; reboot memory is never reused.
    Plant p; p.input.position=.6; p.input.manual=true;
    assert(p.step().position==0);
    assert(!p.control.remembered);
  }
  { // Remember after steady circulation; reuse only after short compatible pause.
    Plant p; p.input.pump=true; p.advance(600);
    assert(p.control.state==ValveState::regulating);
    assert(p.control.remembered);
    const float remembered=p.input.position;
    p.input.pump=false; p.advance(60);
    assert(p.input.position==0);
    p.input.pump=true; p.advance(60);
    assert(std::fabs(p.input.position-remembered)<.005);
    p.input.pump=false; p.advance(1900);
    p.input.pump=true; p.step();
    assert(!p.control.remembered);
  }
  { // Return is rate-limited; fresh high temperature interrupts prepositioning.
    Plant p; p.control.remembered=true; p.control.remembered_position=.8;
    p.control.remembered_target=35;
    // Build genuine remembered pause context.
    p.input.pump=true; p.advance(600);
    p.input.pump=false; p.step();
    p.control.remembered=true; p.control.remembered_position=.8;
    p.control.remembered_target=35;
    p.input.pump=true; p.step();
    float before=p.input.position; p.step();
    assert(p.input.position-before<=.0251);
    p.input.raw=38; p.input.filtered=38;
    p.step(); assert(p.input.position==0);
    assert(p.control.state==ValveState::settling);
  }
  { // Absolute overtemperature closes hot contribution without stopping pump.
    Plant p; p.input.pump=true; p.advance(300);
    p.input.raw=51; p.step();
    assert(p.control.state==ValveState::fault && p.input.position==0 && p.input.pump);
    p.input.raw=35; p.advance(115);
    assert(p.control.state==ValveState::fault);
    p.advance(10); assert(p.control.state!=ValveState::fault);
  }
  { // Relative +8C requires 15 seconds, sensor freshness expires at 30 seconds.
    Plant p; p.input.pump=true; p.advance(300);
    p.input.raw=44; p.step(); p.advance(10);
    assert(p.control.state!=ValveState::fault);
    p.step(); assert(p.control.state==ValveState::fault);
    Plant q; q.input.pump=true; q.advance(300);
    q.step(25,false); assert(q.control.state!=ValveState::fault);
    q.step(5,false); assert(q.control.state==ValveState::fault);
  }
  { // Cooling/manual invalidate a heating position; no competing commands.
    Plant p; p.input.pump=true; p.advance(600);
    assert(p.control.remembered);
    p.input.manual=true; auto output=p.step();
    assert(!p.control.remembered && !output.command);
    p.input.manual=false; p.input.heating=false; p.input.cooling=true;
    output=p.step(); assert(!p.control.remembered && !output.command);
  }
  { // No regulation competes with homing or an idle anti-lock exercise.
    Plant p; p.input.calibrated=false; assert(!p.step().command);
    assert(p.control.state==ValveState::calibrating);
    p.input.calibrated=true; p.input.exercising=true;
    assert(!p.step().command);
  }
  { // Quiet regulation: 1% step and cooldown measured after movement finishes.
    Plant p; p.input.pump=true; p.advance(600);
    p.input.raw=p.input.filtered=31; p.advance(150);
    float previous=p.input.position;
    bool corrected=false;
    for(int i=0;i<30;++i) {
      auto out=p.step();
      if(out.command && p.input.position>previous) {
        assert(p.input.position-previous<=.0101);
        corrected=true; p.control.motion_finished(p.input.now+10); break;
      }
      previous=p.input.position;
    }
    assert(corrected);
    previous=p.input.position; p.advance(90);
    assert(p.input.position==previous);
  }
  { // Pump-pause measurements cannot enter the restarted control filter.
    Plant p; p.input.pump=true; p.advance(600);
    p.input.pump=false; p.input.raw=p.input.filtered=10; p.advance(60);
    p.input.pump=true; p.input.raw=p.input.filtered=35; p.advance(300);
    assert(std::fabs(p.control.average-35)<.001);
  }
  { // A rising supply already approaching the band defers further opening.
    Plant p; p.input.pump=true; p.input.raw=p.input.filtered=31; p.advance(600);
    p.control.config.move_pause=0;
    for(int i=0;i<24;++i) { p.input.raw+=.05f; p.input.filtered=p.input.raw; p.step(); }
    float before=p.input.position;
    for(int i=0;i<12;++i) { p.input.raw+=.05f; p.input.filtered=p.input.raw; p.step(); }
    assert(p.input.position==before);
  }
  std::cout << "10 mixing-controller scenarios passed\n";
}
