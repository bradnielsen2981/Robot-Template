/* This is your dashboard javascript, it has been embedded into dashboard.html */
alert("Loaded");

function shutdown() {
    alert("Trying to shutdown");
    new_ajax_helper('/shutdown'); 
    // Your code here
  };