/* This is your general javascript, it has been embedded into layout.html. 
Any scripts here are available through out the entire website */

shutdown_button.onclick = shutdown;
function shutdown() {
    alert("Shutting Down")
    new_ajax_helper('/shutdown'); 
  };