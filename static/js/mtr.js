let mtrv = new Vue({
    el: "#mtr",

    data () {
        return{
            address: null,
            node: null,
            mtrtime: null,
            hopdata: null
        }
    },

    mounted () {
        axios
            .get("../netmeasuretmp/json/" + (new URLSearchParams(window.location.search)).get("json"))
            .then(response => {
                this.address = response.data.address
                this.node = response.data.node
                this.mtrtime = response.data.time
                this.hopdata = response.data.data
            })
            .catch(error => {
                console.log(error)
                this.errored = true
            })
            .finally(() => this.loading = false)
    },

    computed: {
        style_class: function () {
            let h = new Date().getHours()
            if (h >= 7 && h <= 17){
                return "day"
            }
            else{
                return "night"
            }
        }
    }
});